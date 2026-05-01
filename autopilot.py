#!/usr/bin/env python3
"""
Claude Autopilot v1.0 - Predictive AI Session Intelligence Engine
by Dharmik Soni · github.com/Dharmik2510
"""

import click
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.session_reader import SessionReader
from core.fuel_gauge import FuelGauge
from core.dna_engine import DNAEngine
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
@click.version_option("1.0.0", prog_name="claude-autopilot")
def cli():
    """Claude Autopilot - Predictive AI Session Intelligence for Claude Code."""
    pass


@cli.command()
@click.option("--project", "-p", default=None)
@click.option("--compact", is_flag=True)
@click.option("--refresh", "-r", default=1.0)
def dashboard(project, compact, refresh):
    """Launch the live terminal dashboard."""
    _check_claude_dir()
    reader = SessionReader(CLAUDE_PROJECTS_DIR)
    gauge = FuelGauge()
    dna = DNAEngine()
    anomaly = AnomalyDetector()
    forecaster = CostForecaster(reader)
    dash = AutopilotDashboard(
        reader=reader, gauge=gauge, dna_engine=dna,
        anomaly_detector=anomaly, forecaster=forecaster,
        project_filter=project, compact=compact, refresh_interval=refresh,
    )
    dash.run()


@cli.command()
@click.option("--project", "-p", default=None)
@click.option("--show_all", is_flag=True)
def dna(project, show_all):
    """Show session DNA fingerprints for all projects."""
    _check_claude_dir()
    reader = SessionReader(CLAUDE_PROJECTS_DIR)
    engine = DNAEngine()
    sessions = reader.get_sessions(project_filter=project)
    if not sessions:
        click.echo("No sessions found.")
        return
    click.echo("\n🧬 Session DNA Fingerprints\n")
    for session in sessions[-10:]:
        fp = engine.fingerprint(session)
        click.echo(f"  Project: {session.project_name}")
        click.echo(f"  Session: {session.session_id}")
        click.echo(f"  DNA:     {fp.glyph_string}")
        click.echo(f"  Pattern: {fp.pattern_label}")
        click.echo(f"  Match:   {fp.similarity_label}\n")


@cli.command()
@click.option("--project", "-p", default=None)
@click.option("--apply", is_flag=True)
@click.option("--min-savings", default=1000)
def prune(project, apply, min_savings):
    """Get intelligent context pruning recommendations."""
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
        click.echo("✓ No pruning needed - your context looks clean!")
        return
    total_savings = sum(r.token_count for r in recommendations)
    click.echo(f"\n✂️  Pruning Recommendations  (saves ~{total_savings:,} tokens)\n")
    for rec in sorted(recommendations, key=lambda r: r.token_count, reverse=True):
        if rec.token_count < min_savings:
            continue
        click.echo(f"  {rec.file_path:<35} {rec.token_count:>8,} tok  {rec.reason}")
    if apply:
        pruner.apply(latest, recommendations)
        click.echo("\n✓ Done. Restart Claude Code session to see effect.")
    else:
        click.echo("\nRun with --apply to remove these from your .claude context.")


@cli.command()
@click.option("--days", default=30)
@click.option("--breakdown", is_flag=True)
def forecast(days, breakdown):
    """Monthly cost forecast based on your usage patterns."""
    _check_claude_dir()
    reader = SessionReader(CLAUDE_PROJECTS_DIR)
    forecaster = CostForecaster(reader)
    report = forecaster.generate(horizon_days=days, breakdown=breakdown)
    click.echo("\n💰 Cost Forecast\n")
    click.echo(f"  Today (est):    ${report.today_estimate:.2f}")
    click.echo(f"  This week:      ${report.week_estimate:.2f}")
    click.echo(f"  Projected {days}d: ${report.total_forecast:.2f}")
    click.echo(f"  Peak days:      {chr(44).join(report.peak_days)}")
    click.echo(f"  Cheapest days:  {chr(44).join(report.cheap_days)}")
    click.echo(f"  Tip:            {report.recommendation}")


@cli.command()
@click.option("--top", default=10)
@click.option("--project", "-p", default=None)
def efficiency(top, project):
    """Prompt efficiency analysis and scoring."""
    _check_claude_dir()
    reader = SessionReader(CLAUDE_PROJECTS_DIR)
    sessions = reader.get_sessions(project_filter=project)
    if not sessions:
        click.echo("No session data found.")
        return
    all_turns = []
    for session in sessions:
        for turn in session.turns:
            if turn.input_tokens > 0:
                all_turns.append((turn.efficiency_score, turn))
    all_turns.sort(key=lambda x: x[0], reverse=True)
    click.echo(f"\n📊 Prompt Efficiency  ({len(all_turns)} turns)\n")
    click.echo(f"  Top {top} Most Efficient:")
    for score, turn in all_turns[:top]:
        stars = "★" * min(5, int(score * 5)) + "☆" * (5 - min(5, int(score * 5)))
        preview = (turn.user_message or "")[:60].replace("\n", " ")
        click.echo(f"  {stars}  {preview:<62}  {turn.input_tokens:>5} tok")
    if all_turns:
        avg = sum(s for s, _ in all_turns) / len(all_turns)
        grade = "A+" if avg > 0.8 else "A" if avg > 0.7 else "B+" if avg > 0.6 else "B" if avg > 0.5 else "C"
        click.echo(f"\n  Overall Grade: {grade}  (score: {avg:.2f})")


@cli.command()
@click.option("--project", "-p", default=None)
@click.option("--refresh", "-r", default=2.0)
def watch(project, refresh):
    """Compact watch mode — runs as a sidebar while you code."""
    _check_claude_dir()
    reader = SessionReader(CLAUDE_PROJECTS_DIR)
    gauge = FuelGauge()
    anomaly_det = AnomalyDetector()
    forecaster = CostForecaster(reader)
    click.echo("Claude Autopilot Watch Mode (Ctrl+C to stop)\n")
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
            fuel_pct = int(state.fuel_percent)
            anom_str = f"{anom_count} anomaly" if anom_count else "clean"
            line = (
                f"\r🔋 {fuel_pct:3d}%  "
                f"ETA {state.eta_minutes:.0f}m  "
                f"burn {state.burn_rate:.0f} tok/min  "
                f"turns {latest.turn_count}  "
                f"${today_cost:.2f} today  "
                f"[{anom_str}]   "
            )
            click.echo(line, nl=False)
            time.sleep(refresh)
        except KeyboardInterrupt:
            click.echo("\n\nWatch mode stopped.")
            break


if __name__ == "__main__":
    cli()
