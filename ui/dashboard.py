"""
dashboard.py - Rich TUI Live Dashboard

The main terminal UI for Claude Autopilot. Uses the Rich library
to render a beautiful, real-time dashboard that updates every second.

Layout:
  - Header: Session name, time, version
  - Fuel gauge: Live burn bar with ETA
  - Stats row: Burn rate, turns, total tokens
  - Two-column: Input/Output split | Session DNA bar
  - Context table: Top files with PRUNABLE/HOT/WARM labels
  - Footer: Cost estimate, forecast, efficiency grade, anomaly status
"""

import time
from datetime import datetime
from typing import Optional

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text

from core.anomaly import AnomalyDetector
from core.dna_engine import DNAEngine
from core.forecaster import CostForecaster
from core.fuel_gauge import FuelGauge
from core.session_reader import ClaudeSession, SessionReader

# Cyberpunk color theme
THEME = {
    "header_bg":    "dark_blue",
    "fuel_full":    "bright_green",
    "fuel_warn":    "yellow",
    "fuel_crit":    "bright_red",
    "dna_color":    "cyan",
    "hot_file":     "bright_red",
    "warm_file":    "yellow",
    "cold_file":    "dim white",
    "prune_label":  "bright_magenta",
    "cost_color":   "bright_yellow",
    "accent":       "bright_cyan",
    "dim":          "dim",
    "border":       "bright_blue",
}


class AutopilotDashboard:
    """
    Live Rich TUI dashboard for Claude Autopilot.
    Renders real-time session intelligence with sub-100ms refresh.
    """

    def __init__(
        self,
        reader: SessionReader,
        gauge: FuelGauge,
        dna_engine: DNAEngine,
        anomaly_detector: AnomalyDetector,
        forecaster: CostForecaster,
        project_filter: Optional[str] = None,
        compact: bool = False,
        refresh_interval: float = 1.0,
    ):
        self.reader = reader
        self.gauge = gauge
        self.dna_engine = dna_engine
        self.anomaly_detector = anomaly_detector
        self.forecaster = forecaster
        self.project_filter = project_filter
        self.compact = compact
        self.refresh_interval = refresh_interval
        self.console = Console()

    def run(self):
        with Live(
            self._render(),
            console=self.console,
            refresh_per_second=int(1 / self.refresh_interval),
            screen=True,
        ) as live:
            try:
                while True:
                    time.sleep(self.refresh_interval)
                    live.update(self._render())
            except KeyboardInterrupt:
                self.console.print("\n[dim]Claude Autopilot stopped.[/dim]")

    def _render(self) -> Layout:
        sessions = self.reader.get_sessions(project_filter=self.project_filter)
        if not sessions:
            return self._render_waiting()

        latest = max(sessions, key=lambda s: s.last_updated)
        state = self.gauge.compute(latest)
        fp = self.dna_engine.fingerprint(latest)
        forecast = self.forecaster.generate()
        anomalies = list(self.anomaly_detector.scan(latest))

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="fuel", size=4),
            Layout(name="stats", size=3),
            Layout(name="middle", size=6),
            Layout(name="files", size=8),
            Layout(name="footer", size=3),
        )

        layout["header"].update(self._header_panel(latest))
        layout["fuel"].update(self._fuel_panel(state))
        layout["stats"].update(self._stats_panel(state, latest))

        layout["middle"].split_row(
            Layout(name="split", ratio=1),
            Layout(name="dna", ratio=1),
        )
        layout["middle"]["split"].update(self._token_split_panel(latest))
        layout["middle"]["dna"].update(self._dna_panel(fp))

        layout["files"].update(self._files_panel(latest))
        layout["footer"].update(self._footer_panel(forecast, anomalies, latest))

        return layout

    def _header_panel(self, session: ClaudeSession) -> Panel:
        now = datetime.now().strftime("%H:%M:%S")
        text = Text()
        text.append("  🧠 CLAUDE AUTOPILOT v1.0", style="bold bright_cyan")
        text.append("   |   ", style="dim")
        text.append(f"Session: {session.project_name[:25]}", style="bright_white")
        text.append("   |   ", style="dim")
        text.append(now, style="dim white")
        return Panel(Align.center(text), style="dark_blue", height=3)

    def _fuel_panel(self, state) -> Panel:
        pct = state.fuel_percent
        if pct > 50:
            color = THEME["fuel_full"]
        elif pct > 25:
            color = THEME["fuel_warn"]
        else:
            color = THEME["fuel_crit"]

        progress = Progress(
            TextColumn("  {task.description}", style="bold"),
            BarColumn(bar_width=50, style=color, complete_style=color),
            TaskProgressColumn(),
            TextColumn(f"  ETA: ~{state.eta_minutes:.0f} min", style="dim white"),
            TextColumn(f"  Burn: {state.burn_rate:.0f} tok/min", style=THEME["accent"]),
        )
        task = progress.add_task("Session Fuel", total=100)
        progress.update(task, completed=pct)
        return Panel(Align.center(progress), title="[bold]Fuel Gauge[/bold]", border_style=THEME["border"])

    def _stats_panel(self, state, session: ClaudeSession) -> Panel:
        table = Table.grid(expand=True)
        table.add_column(justify="center")
        table.add_column(justify="center")
        table.add_column(justify="center")
        table.add_column(justify="center")
        table.add_row(
            f"[bold bright_cyan]Turns[/bold bright_cyan]\n[bright_white]{session.turn_count}[/bright_white]",
            f"[bold bright_cyan]Tokens Used[/bold bright_cyan]\n[bright_white]{state.tokens_used:,}[/bright_white]",
            f"[bold bright_cyan]Remaining[/bold bright_cyan]\n[bright_white]{state.tokens_remaining:,}[/bright_white]",
            f"[bold bright_cyan]Trend[/bold bright_cyan]\n[bright_white]{state.trend}[/bright_white]",
        )
        return Panel(table, title="[bold]Session Stats[/bold]", border_style=THEME["border"])

    def _token_split_panel(self, session: ClaudeSession) -> Panel:
        total = session.total_tokens or 1
        in_pct = 100 * session.total_input_tokens / total
        out_pct = 100 * session.total_output_tokens / total
        text = Text()
        text.append(f"  INPUT   {in_pct:.0f}%  ({session.total_input_tokens:,} tok)\n", style="bright_cyan")
        in_bar = chr(0x2588) * int(in_pct / 5) + chr(0x2591) * (20 - int(in_pct / 5))
        text.append(f"  {in_bar}\n\n", style="cyan")
        text.append(f"  OUTPUT  {out_pct:.0f}%  ({session.total_output_tokens:,} tok)\n", style="bright_green")
        out_bar = chr(0x2588) * int(out_pct / 5) + chr(0x2591) * (20 - int(out_pct / 5))
        text.append(f"  {out_bar}\n", style="green")
        return Panel(text, title="[bold]Token Split[/bold]", border_style=THEME["border"])

    def _dna_panel(self, fp) -> Panel:
        text = Text()
        text.append("  DNA  ", style="dim")
        text.append(fp.glyph_string, style="bright_cyan")
        text.append(f"\n\n  Pattern: ", style="dim")
        text.append(fp.pattern_label, style="bright_yellow")
        text.append(f"\n  Similarity: ", style="dim")
        text.append(fp.similarity_label, style="bright_white")
        return Panel(text, title="[bold]Session DNA[/bold]", border_style=THEME["border"])

    def _files_panel(self, session: ClaudeSession) -> Panel:
        weights = session.context_file_weights()
        if not weights:
            return Panel("[dim]No file references yet[/dim]", title="[bold]Context Consumers[/bold]", border_style=THEME["border"])

        table = Table(box=box.SIMPLE, expand=True, show_header=True)
        table.add_column("File", style="bright_white", no_wrap=True)
        table.add_column("Tokens", justify="right", style="bright_cyan")
        table.add_column("Status", justify="center")
        table.add_column("Bar", no_wrap=True)

        max_w = max(weights.values()) or 1
        top_files = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:6]

        for i, (fname, weight) in enumerate(top_files):
            tok_est = int(weight)
            bar_len = max(1, int(20 * weight / max_w))
            bar = chr(0x2588) * bar_len + chr(0x2591) * (20 - bar_len)
            if i == 0:
                status = "[bright_red]HOT[/bright_red]"
            elif i <= 2:
                status = "[yellow]WARM[/yellow]"
            else:
                status = "[bright_magenta]PRUNABLE ✂[/bright_magenta]"
            table.add_row(fname[:35], f"{tok_est:,}", status, f"[cyan]{bar}[/cyan]")

        return Panel(table, title="[bold]Context Consumers[/bold]", border_style=THEME["border"])

    def _footer_panel(self, forecast, anomalies, session) -> Panel:
        anom_str = ("[bright_red]" + str(len(anomalies)) + " anomaly" + ("[/bright_red]") if anomalies
                   else "[bright_green]No anomalies[/bright_green]")
        grade_map = {"A+": "bright_green", "A": "green", "B+": "yellow", "B": "yellow", "C": "red"}
        all_scores = [t.efficiency_score for t in session.turns if t.input_tokens > 0]
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        grade = "A+" if avg_score > 0.8 else "A" if avg_score > 0.7 else "B+" if avg_score > 0.6 else "B" if avg_score > 0.5 else "C"
        grade_color = grade_map.get(grade, "white")

        text = Text()
        text.append(f"  💰 ${forecast.today_estimate:.2f} today", style=THEME["cost_color"])
        text.append("  |  ", style="dim")
        text.append(f"${forecast.total_forecast:.2f}/month forecast", style="dim white")
        text.append("  |  ", style="dim")
        text.append(f"Grade: ", style="dim")
        text.append(grade, style=f"bold {grade_color}")
        text.append("  |  ", style="dim")
        text.append(anom_str)
        text.append("  |  [dim]Ctrl+C to exit[/dim]")
        return Panel(Align.center(text), style="dark_blue", height=3)

    def _render_waiting(self) -> Panel:
        return Panel(
            Align.center(Text("Waiting for Claude Code session data...\n\nStart a Claude Code session to see live analytics.", style="dim")),
            title="Claude Autopilot",
            border_style="blue",
        )
