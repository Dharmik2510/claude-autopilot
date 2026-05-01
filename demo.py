#!/usr/bin/env python3
"""
demo.py - Walks through the Claude Autopilot features using simulated data.

No Claude Code installation required. Useful for getting a feel of the tool
before pointing it at your real ~/.claude/projects/ directory.

Run: python demo.py
"""

import random
import time

from rich import box
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# Simulated session data for the demo (not real)
DEMO_FILES = [
    ("app.py",              8400, "active"),
    ("database.py",         6100, "active"),
    ("api/routes.py",       4200, "active"),
    ("requirements.txt",    3200, "stale"),
    ("package-lock.json",   2800, "stale"),
    ("old_tests/",          1800, "stale"),
]


def demo_banner():
    console.print(Align.center("[bold bright_cyan]Claude Autopilot[/bold bright_cyan]"))
    console.print(Align.center("[dim]Token usage analytics for Claude Code[/dim]"))
    console.print()
    console.print(Align.center("[bright_yellow]DEMO MODE[/bright_yellow]  [dim]- simulated data, not real session info[/dim]"))
    console.print()


def demo_fuel_gauge():
    console.print(Rule("[bold cyan]Live context fuel gauge[/bold cyan]"))
    console.print("[dim]Simulating a session burning through its context window...[/dim]\n")

    tokens_used = 80000
    session_limit = 200000
    burn_rate = 620

    progress = Progress(
        TextColumn("  {task.description}", style="bold"),
        BarColumn(bar_width=50, style="bright_green", complete_style="bright_green"),
        TaskProgressColumn(),
        TextColumn("[cyan]{task.fields[burn]}[/cyan]"),
    )

    try:
        with Live(progress, refresh_per_second=4):
            task = progress.add_task("Fuel", total=session_limit, burn="recent burn calc...")
            for _ in range(30):
                tokens_used += burn_rate + random.randint(-100, 200)
                tokens_used = min(tokens_used, session_limit)
                pct = 100 * tokens_used / session_limit

                if pct > 70:
                    color = "bright_green"
                elif pct > 45:
                    color = "yellow"
                else:
                    color = "bright_red"

                progress.update(
                    task,
                    completed=tokens_used,
                    description=f"[{color}]Fuel[/{color}]",
                    burn=f"recent burn ~{burn_rate} tok/min",
                )
                time.sleep(0.15)
    except KeyboardInterrupt:
        pass
    console.print()


def demo_pruner():
    console.print(Rule("[bold cyan]Context pruning suggestions[/bold cyan]"))
    console.print("[dim]Looking at which files Claude actually touched in recent turns...[/dim]\n")
    time.sleep(0.6)

    table = Table(box=box.ROUNDED, show_header=True, border_style="bright_blue")
    table.add_column("File", style="bright_white", no_wrap=True)
    table.add_column("Tokens (est)", justify="right", style="bright_cyan")
    table.add_column("Status", justify="center")
    table.add_column("Bar", no_wrap=True)
    table.add_column("Reason", style="dim")

    for fname, tokens, status in DEMO_FILES:
        bar_len = max(1, int(30 * tokens / 8400))
        bar = chr(0x2588) * bar_len + chr(0x2591) * (30 - bar_len)
        if status == "active":
            status_fmt = "[bright_green]active[/bright_green]"
            reason = ""
        else:
            status_fmt = "[bright_magenta]stale[/bright_magenta]"
            if "lock" in fname or "requirements" in fname:
                reason = "Auto-generated bloat"
            else:
                reason = "Not referenced in recent turns"

        table.add_row(fname, f"{tokens:,}", status_fmt, f"[cyan]{bar}[/cyan]", reason)

    console.print(table)
    console.print()
    console.print("  [bright_green]Estimated savings if you prune all stale entries: ~7,800 tokens[/bright_green]")
    console.print("  [dim]Run: python autopilot.py prune --apply[/dim]")
    console.print()
    time.sleep(2)


def demo_forecast():
    console.print(Rule("[bold cyan]Cost forecast[/bold cyan]"))
    console.print()

    table = Table(box=box.ROUNDED, border_style="bright_blue")
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bright_white")

    table.add_row("Today (est.)",      "[bright_yellow]$4.20[/bright_yellow]")
    table.add_row("This week",         "[bright_yellow]$19.80[/bright_yellow]")
    table.add_row("Next 30 days",      "[bright_yellow]$127.40[/bright_yellow]")
    table.add_row("Heaviest days",     "[bright_red]Monday, Thursday[/bright_red]")
    table.add_row("Lightest days",     "[bright_green]Saturday, Sunday[/bright_green]")

    console.print(Align.center(table))
    console.print("  [dim]These are estimates based on your past usage. Treat as a rough guide.[/dim]")
    console.print()
    time.sleep(2)


def demo_anomalies():
    console.print(Rule("[bold cyan]Anomaly log[/bold cyan]"))
    console.print("[dim]Turns that consumed unusually large amounts of tokens.[/dim]\n")

    anomalies = [
        ("Turn 7",  "3,847", "6.2x", "Large file ingestion (looks like a full module read)"),
        ("Turn 23", "4,200", "8.2x", "Multi-tool burst (5 tool calls in one turn)"),
    ]

    for turn, tokens, mult, cause in anomalies:
        panel = Panel(
            f"  [bright_cyan]{turn}[/bright_cyan] used [bright_red]{tokens}[/bright_red] tokens  [dim]({mult} session average of 512)[/dim]\n"
            f"  [dim]Likely cause:[/dim] [bright_yellow]{cause}[/bright_yellow]",
            title="[bright_red]Anomaly[/bright_red]",
            border_style="bright_red",
        )
        console.print(panel)
        console.print()

    time.sleep(2)


def main():
    console.clear()
    demo_banner()
    time.sleep(1)

    demos = [
        ("Fuel gauge",          demo_fuel_gauge),
        ("Context pruning",     demo_pruner),
        ("Cost forecast",       demo_forecast),
        ("Anomaly detection",   demo_anomalies),
    ]

    for name, fn in demos:
        try:
            fn()
        except KeyboardInterrupt:
            console.print(f"  [dim]Skipped {name}[/dim]\n")
            continue

    console.print(Rule())
    console.print(Align.center("[bold bright_cyan]Claude Autopilot[/bold bright_cyan]  -  [dim]github.com/Dharmik2510/claude-autopilot[/dim]"))
    console.print()


if __name__ == "__main__":
    main()
