#!/usr/bin/env python3
"""
Claude Autopilot - Token usage analytics for Claude Code

An honest, descriptive tool that reads ~/.claude/projects/ session data
and helps you understand where your context tokens are going.

No fake predictions, no gimmicky scores. Just useful signal.

by Dharmik Soni - github.com/Dharmik2510
"""

import click
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.session_reader import SessionReader
from core.fuel_gauge import FuelGauge
from core.pruner import ContextPruner
from core.forecaster import CostForecaster
from core.anomaly import AnomalyDetector
from ui.dashboard import AutopilotDashboard

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _check_claude_dir():
    if not CLAUDE_PROJECTS_DIR.exists():
        click.echo("ERROR: ~/.claude/projects/ not found. Install Claude Code first.", err=True)
        sys.exit(1)


@click.group()
@click.version_option("0.1.0", prog_name="claude-autopilot")
def cli():
    """Claude Autopilot - Token usage analytics for Claude Code."""
    pass


@cli.command()
@click.option("--project", "-p", default=None, help="Filter to a specific project")
@click.option("--refresh", "-r", default=2.0, help="Refresh interval in seconds")
def dashboard(project, refresh):
    """Launch the live terminal dashboard."""
    _check_claude_dir()
    reader = SessionReader(CLAUDE_PROJECTS_DIR)
    gauge = FuelGauge()
    anomaly = AnomalyDetector()
    forecaster = CostForecaster(reader)
    dash = AutopilotDashboard(
        reader=reader,
        gauge=gauge,
        anomaly_detector=anomaly,
        forecaster=forecaster,
        project_filter=project,
        refresh_interval=refresh,
    )
    dash.run()


@cli.command()
@click.option("--project", "-p", default=None, help="Filter to a specific project")
@click.option("--apply", is_flag=True, help="Actually remove suggestions from .claude config")
@click.option("--min-savings", default=1000, help="Hide suggestions saving fewer tokens than this")
def prune(project, apply, min_savings):
    """
    Suggest files to remove from your active context to save tokens.

    This is the headline feature. Looks at which files Claude actually
    referenced in your recent session turns and flags context that has
    gone stale or is auto-generated bloat (lock files, etc).
    """
    _check_claude_dir()
    reader = SessionReader(CLAUDE_PROJECTS_DIR)
    pruner = ContextPruner(reader)
    sessions = reader.get_sessions(project_filter=project)
    if not sessions:
        click.echo("No sessions found.")
        return
    latest = max(sessions, key=lambda s: s.last_updated)
    recommendations = pruner.analyze(latest)
    if not recommendations:
        click.echo("No prunable context detected in the latest session.")
        return
    total = sum(r.token_count for r in recommendations if r.token_count >= min_savings)
    click.echo(f"\nContext pruning suggestions  (estimated savings: {total:,} tokens)\n")
    for rec in sorted(recommendations, key=lambda r: r.token_count, reverse=True):
        if rec.token_count < min_savings:
            continue
        click.echo(f"  {rec.file_path:<35} {rec.token_count:>8,} tok  {rec.reason}")
    if apply:
        removed = pruner.apply(latest, recommendations)
        click.echo(f"\nRemoved {removed} entries from .claude config.")
    else:
        click.echo("\nRun with --apply to update your .claude config.")


@cli.command()
@click.option("--days", default=30, help="Forecast horizon in days")
@click.option("--breakdown", is_flag=True, help="Show day-by-day estimates")
def forecast(days, breakdown):
    """
    Estimate your monthly Claude Code spend based on past usage.

    Uses your own daily usage averages by day-of-week to project forward.
    Treat the numbers as a rough guide, not a guarantee.
    """
    _check_claude_dir()
    reader = SessionReader(CLAUDE_PROJECTS_DIR)
    forecaster = CostForecaster(reader)
    report = forecaster.generate(horizon_days=days, breakdown=breakdown)
    click.echo("\nCost estimate (based on your past usage)\n")
    click.echo(f"  Today (est):    ${report.today_estimate:.2f}")
    click.echo(f"  This week:      ${report.week_estimate:.2f}")
    click.echo(f"  Next {days} days:   ${report.total_forecast:.2f}")
    click.echo(f"  Heaviest days:  {chr(44).join(report.peak_days)}")
    click.echo(f"  Lightest days:  {chr(44).join(report.cheap_days)}")


@cli.command()
@click.option("--project", "-p", default=None, help="Filter to a specific project")
@click.option("--threshold", default=2.5, help="Z-score threshold (higher = stricter)")
@click.option("--limit", default=20, help="Max anomalies to show")
def anomalies(project, threshold, limit):
    """
    Show turns that consumed unusually large amounts of tokens.

    Uses z-score analysis on per-turn token deltas. Useful for finding
    accidental large file reads or runaway tool calls in past sessions.
    """
    _check_claude_dir()
    reader = SessionReader(CLAUDE_PROJECTS_DIR)
    detector = AnomalyDetector(z_threshold=threshold)
    sessions = reader.get_sessions(project_filter=project)
    detected = []
    for session in sessions:
        for anomaly in detector.scan(session):
            detected.append((session, anomaly))
    if not detected:
        click.echo("No anomalies detected in your sessions.")
        return
    click.echo(f"\nAnomaly log  ({len(detected)} detected)\n")
    for session, anomaly in detected[-limit:]:
        click.echo(f"  Project: {session.project_name}  |  Turn {anomaly.turn_number}  |  {anomaly.timestamp}")
        click.echo(f"    Used {anomaly.actual_tokens:,} tokens  ({anomaly.z_score:.1f}x above session average of {anomaly.baseline_tokens:,.0f})")
        click.echo(f"    Likely cause: {anomaly.probable_cause}")
        click.echo(f"    Suggestion:   {anomaly.recommendation}\n")


@cli.command()
@click.option("--project", "-p", default=None, help="Filter to a specific project")
@click.option("--refresh", "-r", default=3.0, help="Refresh interval in seconds")
def watch(project, refresh):
    """
    Compact one-line status, refreshed in place. Good for a sidebar pane.
    """
    _check_claude_dir()
    reader = SessionReader(CLAUDE_PROJECTS_DIR)
    gauge = FuelGauge()
    anomaly_det = AnomalyDetector()
    forecaster = CostForecaster(reader)
    click.echo("Claude Autopilot watch mode (Ctrl+C to stop)\n")
    while True:
        try:
            sessions = reader.get_sessions(project_filter=project)
            if not sessions:
                click.echo("\rWaiting for session data...", nl=False)
                time.sleep(refresh)
                continue
            latest = max(sessions, key=lambda s: s.last_updated)
            state = gauge.compute(latest)
            today_cost = forecaster.today_estimate()
            anom_count = len(list(anomaly_det.scan(latest)))
            anom_str = f"{anom_count} anomaly" if anom_count else "clean"
            line = (
                f"\r  Fuel {int(state.fuel_percent):3d}%  "
                f"|  used {state.tokens_used:,}  "
                f"|  recent burn {state.recent_burn_rate:.0f} tok/min  "
                f"|  ${today_cost:.2f} today  "
                f"|  {anom_str}        "
            )
            click.echo(line, nl=False)
            time.sleep(refresh)
        except KeyboardInterrupt:
            click.echo("\n\nStopped.")
            break


if __name__ == "__main__":
    cli()
