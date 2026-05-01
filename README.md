# claude-autopilot

Token usage analytics for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Reads the JSONL session files Claude Code writes to `~/.claude/projects/` and turns them into a local dashboard, prune suggestions, and a rough cost forecast.

> **Status: experimental.** This is a personal project. It will give you useful signal about where your tokens are going, but it is not (yet) a polished tool. See "Honest limitations" below.

Inspired by [nateherkai/token-dashboard](https://github.com/nateherkai/token-dashboard) - the original is more complete and has a real web UI with charts. This project takes a different angle: it focuses on **pruning suggestions** and **anomaly detection** for the latest session, and now ships a minimal browser dashboard of its own.

## What it does

1. **Web dashboard** (`autopilot.py serve`) - opens a local page at `http://127.0.0.1:8080/` showing totals, per-project breakdown, prune suggestions, and anomalies. Stdlib HTTP server, vanilla JS, no external CDN, no telemetry. Auto-refreshes every 30 seconds.
2. **Prune suggestions** (`autopilot.py prune`) - flags files that appear stale in your latest session's context (lockfiles, files referenced once long ago, etc.) so you can decide whether to drop them.
3. **Anomaly log** (`autopilot.py anomalies`) - z-score scan of per-turn token deltas. Useful for spotting the one turn where you accidentally fed in a 50k-token file.
4. **Cost forecast** (`autopilot.py forecast`) - rough monthly projection based on your day-of-week usage pattern. **API pricing only** - if you are on Pro or Max your real cost is different.
5. **Terminal dashboard** (`autopilot.py dashboard`) - same data as the web UI, in a Rich TUI. Use whichever you prefer.
6. **Watch** (`autopilot.py watch`) - one-line live status in the terminal.

## What it does not do

- No predictive ETA for when your context will run out. Token consumption is too bursty for that prediction to be honest.
- No "session DNA fingerprint" or efficiency grade. Removed - they were gimmicks.
- No subagent or Skill-level attribution. The original token-dashboard does this.
- No interactive charts in the web UI yet. Just real numbers in clean cards and tables.
- No persistent SQLite cache yet. Sessions are re-parsed on each request (fast for small histories, slower for power users).

## How the numbers are counted

Claude Code writes each assistant response to disk **2-3 times** while it streams - the same API message gets re-snapshotted as the output grows. If a tool naively sums every JSONL row, the totals will be inflated.

`claude-autopilot` dedupes by `message.id` so the totals match what Anthropic actually billed. This is the same approach Nate Herkelman documents in token-dashboard. If you cross-check against a tool that does not dedup (some early scripts do not), expect this dashboard's numbers to be lower and closer to your real bill.

## Install

```bash
git clone https://github.com/Dharmik2510/claude-autopilot.git
cd claude-autopilot
pip install -r requirements.txt
```

Requires Python 3.8+. The web server uses only stdlib; the terminal dashboard uses `rich` and `click`.

## Usage

```bash
# Open the browser dashboard
python autopilot.py serve

# Or run the terminal dashboard
python autopilot.py dashboard

# Prune suggestions for the latest session
python autopilot.py prune

# Anomaly log
python autopilot.py anomalies

# Rough cost forecast (API rates)
python autopilot.py forecast --days 30
```

## Privacy

Nothing leaves your machine. The web server binds to `127.0.0.1` only - never `0.0.0.0` - so other devices on your network cannot reach it. The HTML page loads no external scripts, fonts, or stylesheets. There is no telemetry and no remote calls of any kind.

## Honest limitations

- **Cost numbers are API-rate.** If you are on a Pro or Max plan, what you actually pay is your subscription, not the per-token math shown here. Treat the cost line as "what this would cost on the API," not as your bill.
- **The forecast is a back-of-envelope projection**, not a model. It assumes the next 30 days look like the previous 30. Holidays, deadlines, and one-off heavy projects will throw it off.
- **The pruner is conservative.** It will not delete anything unless you pass `--apply`. Even then, double-check the suggestions - it can over-flag files you actually still need.
- **No tests yet.** I run it on my own `~/.claude/` and the numbers line up with what I see in [ccusage](https://github.com/ryoppippi/ccusage), but I have not written a proper test suite.
- **Single-session web UI.** The browser dashboard summarises everything but the prune list and anomaly list only cover the latest session.

## Why this exists

I saw Nate Herkelman's LinkedIn post about his Claude Code token dashboard, liked the idea, and wanted to build something with a slightly different shape - more focused on "what should I do about it" (prune, watch for anomalies) than on browsing every prompt you have ever sent. If you want the full browseable history with charts, use [his project](https://github.com/nateherkai/token-dashboard); if you want a quick "what is wasting tokens in my latest session" view, this one might suit you.

## License

MIT. See [LICENSE](LICENSE).

---
Built by [Dharmik Soni](https://github.com/Dharmik2510). Bug reports and PRs welcome.
