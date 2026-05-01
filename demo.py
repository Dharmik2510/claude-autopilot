#!/usr/bin/env python3
"""
demo.py - Claude Autopilot Demo Mode

Runs a fully animated demo of all Claude Autopilot features
using simulated session data. No Claude Code installation required.

Usage: python demo.py

This is the file you run to show others what Claude Autopilot does
before they have any real session data.
"""

import math
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

DEMO_BANNER = """
 ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗
██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝
██║     ██║     ███████║██║   ██║██║  ██║█████╗  
██║     ██║     ██╔══██║██║   ██║██║  ██║██╔══╝  
╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝███████╗
 ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝
     █████╗ ██╗   ██╗████████╗ ██████╗ ██████╗ ██╗██╗      ██████╗ ████████╗
    ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔══██╗██║██║     ██╔═══██╗╚══██╔══╝
    ███████║██║   ██║   ██║   ██║   ██║██████╔╝██║██║     ██║   ██║   ██║   
    ██╔══██║██║   ██║   ██║   ██║   ██║██╔═══╝ ██║██║     ██║   ██║   ██║   
    ██║  ██║╚██████╔╝   ██║   ╚██████╔╝██║     ██║███████╗╚██████╔╝   ██║   
    ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═╝     ╚═╝╚══════╝ ╚═════╝    ╚═╝   
"""

# Simulated session data
DEMO_FILES = [
    ("app.py", 8400, "HOT"),
    ("database.py", 6100, "WARM"),
    ("api/routes.py", 4200, "WARM"),
    ("requirements.txt", 3200, "PRUNABLE"),
    ("package-lock.json", 2800, "PRUNABLE"),
    ("old_tests/", 1800, "STALE"),
]

DEMO_DNAS = [
    ("my-saas-app",     chr(0x2581) + chr(0x2583) + chr(0x2585) + chr(0x2587) + chr(0x2588) + chr(0x2586) + chr(0x2583) + chr(0x2581) + chr(0x2582) + chr(0x2585) + chr(0x2587) + chr(0x2588) + chr(0x2585) + chr(0x2582) + chr(0x2581) + chr(0x2583) + chr(0x2586) + chr(0x2588) + chr(0x2587) + chr(0x2584) + chr(0x2582) + chr(0x2581) + chr(0x2582) + chr(0x2584) + chr(0x2586) + chr(0x2587) + chr(0x2588) + chr(0x2585) + chr(0x2583) + chr(0x2582) + chr(0x2581), "Feature Build", "91% match to your feature sessions"),
    ("api-refactor",    chr(0x2581) + chr(0x2581) + chr(0x2582) + chr(0x2582) + chr(0x2584) + chr(0x2585) + chr(0x2587) + chr(0x2588) + chr(0x2585) + chr(0x2583) + chr(0x2581) + chr(0x2581) + chr(0x2582) + chr(0x2584) + chr(0x2588) + chr(0x2587) + chr(0x2585) + chr(0x2583) + chr(0x2582) + chr(0x2581), "Refactor", "78% match to your refactor sessions"),
    ("bug-hunt-auth",   chr(0x2588) + chr(0x2586) + chr(0x2583) + chr(0x2581) + chr(0x2581) + chr(0x2582) + chr(0x2588) + chr(0x2587) + chr(0x2584) + chr(0x2581) + chr(0x2581) + chr(0x2582) + chr(0x2581) + chr(0x2583) + chr(0x2587) + chr(0x2588) + chr(0x2585) + chr(0x2582) + chr(0x2581), "Bug Fix", "95% match to your debugging sessions"),
]


def demo_banner():
    console.print(DEMO_BANNER, style="bold bright_cyan")
    console.print()
    console.print(Align.center("[bold bright_yellow]DEMO MODE[/bold bright_yellow]  [dim]— Simulated session data[/dim]"))
    console.print()


def demo_dna():
    console.print(Rule("[bold cyan]Session DNA Fingerprints[/bold cyan]"))
    console.print()
    for project, dna, pattern, sim in DEMO_DNAS:
        console.print(f"  [dim]Project:[/dim] [bright_white]{project}[/bright_white]")
        console.print(f"  [dim]DNA:    [/dim] [bright_cyan]{dna}[/bright_cyan]")
        console.print(f"  [dim]Pattern:[/dim] [bright_yellow]{pattern}[/bright_yellow]")
        console.print(f"  [dim]Match:  [/dim] [white]{sim}[/white]")
        console.print()
    time.sleep(2)


def demo_fuel_gauge():
    console.print(Rule("[bold cyan]Live Token Fuel Gauge[/bold cyan]"))
    console.print("[dim]Simulating live session burn... (Ctrl+C to skip)[/dim]\n")

    tokens_used = 80000
    session_limit = 200000
    burn_rate = 620

    progress = Progress(
        TextColumn("  {task.description}", style="bold"),
        BarColumn(bar_width=50, style="bright_green", complete_style="bright_green"),
        TaskProgressColumn(),
        TextColumn("[dim]{task.fields[eta]}[/dim]"),
        TextColumn("[cyan]{task.fields[burn]}[/cyan]"),
    )

    try:
        with Live(progress, refresh_per_second=4) as live:
            task = progress.add_task(
                "Session Fuel",
                total=session_limit,
                eta="ETA ~calc...",
                burn="burn ~calc...",
            )
            for _ in range(40):
                tokens_used += burn_rate + random.randint(-100, 200)
                tokens_used = min(tokens_used, session_limit)
                remaining = session_limit - tokens_used
                eta = remaining / burn_rate
                pct = 100 * tokens_used / session_limit

                # Color changes as fuel depletes
                if pct > 70:
                    color = "bright_green"
                elif pct > 45:
                    color = "yellow"
                else:
                    color = "bright_red"

                progress.update(
                    task,
                    completed=tokens_used,
                    description=f"[{color}]Session Fuel[/{color}]",
                    eta=f"ETA ~{eta/60:.0f} min",
                    burn=f"Burn: {burn_rate:,} tok/min",
                )
                time.sleep(0.15)
    except KeyboardInterrupt:
        pass
    console.print()


def demo_pruner():
    console.print(Rule("[bold cyan]Smart Context Pruning[/bold cyan]"))
    console.print("[dim]Analyzing active session context...\n[/dim]")
    time.sleep(0.8)

    table = Table(box=box.ROUNDED, show_header=True, border_style="bright_blue")
    table.add_column("File", style="bright_white", no_wrap=True)
    table.add_column("Tokens", justify="right", style="bright_cyan")
    table.add_column("Status", justify="center")
    table.add_column("Bar (30 chars)", no_wrap=True)
    table.add_column("Reason", style="dim")

    for fname, tokens, status in DEMO_FILES:
        bar_len = max(1, int(30 * tokens / 8400))
        bar = chr(0x2588) * bar_len + chr(0x2591) * (30 - bar_len)
        if status == "HOT":
            status_fmt = "[bright_red]HOT[/bright_red]"
        elif status == "WARM":
            status_fmt = "[yellow]WARM[/yellow]"
        elif status == "PRUNABLE":
            status_fmt = "[bright_magenta]PRUNABLE ✂[/bright_magenta]"
        else:
            status_fmt = "[dim]STALE[/dim]"

        reason = ""
        if status == "PRUNABLE":
            reason = "Auto-generated file"
        elif status == "STALE":
            reason = "Not referenced in 12 turns"

        table.add_row(fname, f"{tokens:,}", status_fmt, f"[cyan]{bar}[/cyan]", reason)

    console.print(table)
    console.print()
    console.print("  [bright_green]✂  Pruning could save 6,000 tokens (12% of context)[/bright_green]")
    console.print("  [dim]Run: python autopilot.py prune --apply[/dim]")
    console.print()
    time.sleep(2)


def demo_forecast():
    console.print(Rule("[bold cyan]Monthly Cost Forecast[/bold cyan]"))
    console.print()

    table = Table(box=box.ROUNDED, border_style="bright_blue")
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bright_white")

    table.add_row("Today (est.)",    "[bright_yellow]$4.20[/bright_yellow]")
    table.add_row("This week",       "[bright_yellow]$19.80[/bright_yellow]")
    table.add_row("30-day forecast", "[bright_yellow]$127.40[/bright_yellow]")
    table.add_row("Peak days",       "[bright_red]Monday, Thursday[/bright_red]")
    table.add_row("Cheapest days",   "[bright_green]Saturday, Sunday[/bright_green]")
    table.add_row("Recommendation",  "[dim]Batch large file reads on Monday mornings,[/dim]\n[dim]lightweight sessions on weekends.[/dim]")

    console.print(Align.center(table))
    console.print()
    time.sleep(2)


def demo_anomalies():
    console.print(Rule("[bold cyan]Anomaly Detection[/bold cyan]"))
    console.print()

    anomalies = [
        ("Turn 7",  "3,847", "6.2x", "Large file ingestion (requirements.txt or full module)"),
        ("Turn 23", "4,200", "8.2x", "Multi-tool burst (5 tool calls in single turn)"),
    ]

    for turn, tokens, mult, cause in anomalies:
        panel = Panel(
            f"  [bright_cyan]{turn}[/bright_cyan] consumed [bright_red]{tokens}[/bright_red] tokens  [dim]({mult} above session average of 512)[/dim]\n"
            f"  [dim]Cause:[/dim]  [bright_yellow]{cause}[/bright_yellow]\n"
            f"  [dim]Fix:  [/dim]  [white]Use targeted queries instead of full file reads[/white]",
            title="[bright_red]⚡ ANOMALY DETECTED[/bright_red]",
            border_style="bright_red",
        )
        console.print(panel)
        console.print()

    time.sleep(2)


def demo_efficiency():
    console.print(Rule("[bold cyan]Prompt Efficiency Scores[/bold cyan]"))
    console.print()

    prompts = [
        ("★★★★★", "Fix null pointer in auth.py line 47",         "  312"),
        ("★★★★☆", "Add dark mode toggle to settings panel",      "  890"),
        ("★★★☆☆", "Refactor the entire API middleware layer",    "4,200"),
        ("★★☆☆☆", "Explain how this whole codebase works",       "9,100"),
        ("★☆☆☆☆", "Read all files and suggest improvements",     "18,400"),
    ]

    table = Table(box=box.SIMPLE, show_header=True)
    table.add_column("Score", style="bright_yellow")
    table.add_column("Prompt", style="bright_white", no_wrap=False)
    table.add_column("Tokens", justify="right", style="dim")

    for stars, prompt, tokens in prompts:
        table.add_row(stars, prompt, tokens)

    console.print(table)
    console.print("  Overall Efficiency Grade: [bold bright_green]B+[/bold bright_green]  (top 22% of Claude Code users)")
    console.print()
    time.sleep(2)


def main():
    console.clear()
    demo_banner()
    time.sleep(1)

    demos = [
        ("DNA Fingerprints",    demo_dna),
        ("Fuel Gauge",          demo_fuel_gauge),
        ("Context Pruning",     demo_pruner),
        ("Cost Forecast",       demo_forecast),
        ("Anomaly Detection",   demo_anomalies),
        ("Efficiency Scoring",  demo_efficiency),
    ]

    for name, fn in demos:
        try:
            fn()
        except KeyboardInterrupt:
            console.print(f"  [dim]Skipped {name}[/dim]\n")
            continue

    console.print(Rule())
    console.print()
    console.print(Align.center("[bold bright_cyan]Claude Autopilot[/bold bright_cyan] — [bright_white]github.com/Dharmik2510/claude-autopilot[/bright_white]"))
    console.print(Align.center("[dim]Stop flying blind. Start piloting your AI sessions.[/dim]"))
    console.print()


if __name__ == "__main__":
    main()
