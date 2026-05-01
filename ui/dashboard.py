"""
dashboard.py - Live terminal dashboard for Claude Autopilot

Renders a clean, descriptive dashboard of your current Claude Code session:
  - Fuel gauge (tokens used vs. context window remaining)
  - Recent burn rate (tokens per minute over last few turns)
  - Top context consumers with stale/active indicators
  - Cost estimate for today + monthly forecast
  - Anomaly count if any spikes detected

No predictive ETAs, no fingerprints, no efficiency grades. Just signal.
"""

import time
from datetime import datetime
from typing import Optional

from rich import box
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
from rich.table import Table
from rich.text import Text

from core.anomaly import AnomalyDetector
from core.forecaster import CostForecaster
from core.fuel_gauge import FuelGauge
from core.session_reader import ClaudeSession, SessionReader


class AutopilotDashboard:
    """Live Rich TUI dashboard."""

    def __init__(
        self,
        reader: SessionReader,
        gauge: FuelGauge,
        anomaly_detector: AnomalyDetector,
        forecaster: CostForecaster,
        project_filter: Optional[str] = None,
        refresh_interval: float = 2.0,
    ):
        self.reader = reader
        self.gauge = gauge
        self.anomaly_detector = anomaly_detector
        self.forecaster = forecaster
        self.project_filter = project_filter
        self.refresh_interval = refresh_interval
        self.console = Console()

    def run(self):
        with Live(
            self._render(),
            console=self.console,
            refresh_per_second=max(1, int(1 / self.refresh_interval)),
            screen=True,
        ) as live:
            try:
                while True:
                    time.sleep(self.refresh_interval)
                    live.update(self._render())
            except KeyboardInterrupt:
                self.console.print("\n[dim]Stopped.[/dim]")

    def _render(self) -> Layout:
        sessions = self.reader.get_sessions(project_filter=self.project_filter)
        if not sessions:
            return Panel(
                Align.center(Text(
                    "Waiting for Claude Code session data...\n\n"
                    "Start a Claude Code session to see live analytics.",
                    style="dim",
                )),
                title="Claude Autopilot",
                border_style="blue",
            )

        latest = max(sessions, key=lambda s: s.last_updated)
        state = self.gauge.compute(latest)
        forecast = self.forecaster.generate()
        anomalies = list(self.anomaly_detector.scan(latest))

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="fuel", size=4),
            Layout(name="stats", size=3),
            Layout(name="files", size=12),
            Layout(name="footer", size=3),
        )

        layout["header"].update(self._header_panel(latest))
        layout["fuel"].update(self._fuel_panel(state))
        layout["stats"].update(self._stats_panel(state, latest))
        layout["files"].update(self._files_panel(latest))
        layout["footer"].update(self._footer_panel(forecast, anomalies))
        return layout

    def _header_panel(self, session: ClaudeSession) -> Panel:
        now = datetime.now().strftime("%H:%M:%S")
        text = Text()
        text.append("  Claude Autopilot", style="bold bright_cyan")
        text.append("   |   ", style="dim")
        text.append(f"Project: {session.project_name[:30]}", style="bright_white")
        text.append("   |   ", style="dim")
        text.append(now, style="dim white")
        return Panel(Align.center(text), border_style="blue", height=3)

    def _fuel_panel(self, state) -> Panel:
        pct = state.fuel_percent
        if pct > 50:
            color = "bright_green"
        elif pct > 25:
            color = "yellow"
        else:
            color = "bright_red"

        progress = Progress(
            TextColumn("  {task.description}", style="bold"),
            BarColumn(bar_width=50, style=color, complete_style=color),
            TaskProgressColumn(),
            TextColumn(f"  Recent burn: {state.recent_burn_rate:.0f} tok/min", style="bright_cyan"),
        )
        task = progress.add_task("Fuel", total=100)
        progress.update(task, completed=pct)
        return Panel(Align.center(progress), title="[bold]Context Fuel[/bold]", border_style="bright_blue")

    def _stats_panel(self, state, session: ClaudeSession) -> Panel:
        table = Table.grid(expand=True)
        table.add_column(justify="center")
        table.add_column(justify="center")
        table.add_column(justify="center")
        table.add_row(
            f"[dim]Turns[/dim]\n[bright_white]{session.turn_count}[/bright_white]",
            f"[dim]Tokens used[/dim]\n[bright_white]{state.tokens_used:,}[/bright_white]",
            f"[dim]Remaining[/dim]\n[bright_white]{state.tokens_remaining:,}[/bright_white]",
        )
        return Panel(table, title="[bold]Session Stats[/bold]", border_style="bright_blue")

    def _files_panel(self, session: ClaudeSession) -> Panel:
        weights = session.context_file_weights()
        if not weights:
            return Panel(
                "[dim]No file references yet in this session.[/dim]",
                title="[bold]Top Context Consumers[/bold]",
                border_style="bright_blue",
            )

        # Build a stale-detection map: which files appeared in the recent half of turns?
        n = session.turn_count
        recent_files = set()
        for turn in session.turns[max(0, n // 2):]:
            for f in turn.files_referenced:
                recent_files.add(f)

        table = Table(box=box.SIMPLE, expand=True, show_header=True)
        table.add_column("File", style="bright_white", no_wrap=True)
        table.add_column("Tokens (est)", justify="right", style="bright_cyan")
        table.add_column("Status", justify="center")
        table.add_column("Bar", no_wrap=True)

        max_w = max(weights.values()) or 1
        top_files = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:8]

        for fname, weight in top_files:
            tok_est = int(weight)
            bar_len = max(1, int(20 * weight / max_w))
            bar = chr(0x2588) * bar_len + chr(0x2591) * (20 - bar_len)
            if fname in recent_files:
                status = "[bright_green]active[/bright_green]"
            else:
                status = "[bright_magenta]stale (prunable)[/bright_magenta]"
            table.add_row(fname[:35], f"{tok_est:,}", status, f"[cyan]{bar}[/cyan]")

        return Panel(table, title="[bold]Top Context Consumers[/bold]", border_style="bright_blue")

    def _footer_panel(self, forecast, anomalies) -> Panel:
        anom_str = (
            f"[bright_red]{len(anomalies)} anomaly[/bright_red]"
            if anomalies else "[bright_green]no anomalies[/bright_green]"
        )
        text = Text()
        text.append(f"  Today: ${forecast.today_estimate:.2f}", style="bright_yellow")
        text.append("   |   ", style="dim")
        text.append(f"~${forecast.total_forecast:.2f}/month forecast", style="dim white")
        text.append("   |   ", style="dim")
        text.append(anom_str)
        text.append("   |   [dim]Ctrl+C to exit[/dim]")
        return Panel(Align.center(text), border_style="blue", height=3)
