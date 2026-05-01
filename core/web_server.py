"""
web_server.py - Minimal local dashboard server for claude-autopilot.

Stdlib only. Binds to 127.0.0.1 by design - we never expose your prompt
history to the local network. The page is a single static HTML file plus
one JSON endpoint that returns aggregates computed from your real session
files. No telemetry, no external CDN, no fonts loaded from the internet.
"""

import json
import http.server
import socketserver
import webbrowser
from pathlib import Path
from typing import List

from .session_reader import SessionReader, ClaudeSession
from .pruner import ContextPruner
from .forecaster import CostForecaster
from .anomaly import AnomalyDetector


WEB_DIR = Path(__file__).resolve().parent.parent / "ui" / "web"


def _summary_payload(reader: SessionReader) -> dict:
    sessions: List[ClaudeSession] = reader.get_sessions()
    pruner = ContextPruner()
    detector = AnomalyDetector()
    forecaster = CostForecaster(reader)

    total_input = sum(s.total_input_tokens for s in sessions)
    total_output = sum(s.total_output_tokens for s in sessions)
    total_cache_read = sum(s.total_cache_read_tokens for s in sessions)
    total_cache_write = sum(s.total_cache_write_tokens for s in sessions)
    total_turns = sum(s.turn_count for s in sessions)

    by_project: dict = {}
    for s in sessions:
        d = by_project.setdefault(s.project_name, {"sessions": 0, "tokens": 0})
        d["sessions"] += 1
        d["tokens"] += s.total_tokens
    project_rows = sorted(
        ({"name": k, **v} for k, v in by_project.items()),
        key=lambda r: r["tokens"],
        reverse=True,
    )[:10]

    latest = max(sessions, key=lambda s: s.last_updated) if sessions else None
    prune_rows = []
    anomaly_rows = []
    if latest:
        for r in pruner.analyze(latest):
            prune_rows.append({
                "file": r.file_path,
                "tokens": r.token_count,
                "reason": r.reason,
            })
        for a in detector.scan(latest):
            anomaly_rows.append({
                "turn": a.turn_number,
                "tokens": a.actual_tokens,
                "z_score": round(a.z_score, 2),
                "cause": a.probable_cause,
            })
    prune_rows.sort(key=lambda r: r["tokens"], reverse=True)
    prune_rows = prune_rows[:15]

    return {
        "totals": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cache_read_tokens": total_cache_read,
            "cache_write_tokens": total_cache_write,
            "sessions": len(sessions),
            "turns": total_turns,
        },
        "today_cost_usd": round(forecaster.today_estimate(), 4),
        "projects": project_rows,
        "latest_session": {
            "id": latest.session_id if latest else None,
            "project": latest.project_name if latest else None,
            "turns": latest.turn_count if latest else 0,
            "total_tokens": latest.total_tokens if latest else 0,
        },
        "prune_suggestions": prune_rows,
        "anomalies": anomaly_rows,
        "notes": [
            "Token totals are deduped by message.id, so they reflect what the API actually billed.",
            "All pricing is API-rate. If you are on Pro or Max your real cost is different.",
            "This server only binds to 127.0.0.1 and serves no external assets.",
        ],
    }


def make_handler(reader: SessionReader):
    web_dir = str(WEB_DIR)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=web_dir, **kwargs)

        def log_message(self, fmt, *args):  # silence default access log
            return

        def do_GET(self):
            if self.path.startswith("/api/summary"):
                try:
                    payload = _summary_payload(reader)
                    body = json.dumps(payload).encode("utf-8")
                except Exception as e:  # pragma: no cover - defensive
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path in ("/", ""):
                self.path = "/index.html"
            return super().do_GET()

    return Handler


def serve(reader: SessionReader, port: int = 8080, open_browser: bool = True) -> None:
    handler = make_handler(reader)
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{port}/"
        print(f"claude-autopilot web UI serving at {url}")
        print("Bound to 127.0.0.1 only. Press Ctrl+C to stop.")
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
