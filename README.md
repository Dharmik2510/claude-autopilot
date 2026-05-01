# Claude Autopilot

**Token usage analytics for Claude Code.** A small, honest CLI that reads your `~/.claude/projects/` session data and helps you understand where your context tokens are going.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Status](https://img.shields.io/badge/status-experimental-orange?style=flat-square)](#status)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

> Inspired by Nate Herkelman’s Claude Code dashboard. I wanted to push the idea further toward something *actionable* (what should I cut?) rather than just descriptive (here is what happened).

---

## Status

This is an early-stage personal project, not a polished product. Numbers shown by the tool are estimates, not guarantees. I am sharing it because the **context pruning** feature has saved me real tokens on real sessions and I think it could help others too. Feedback and PRs welcome.

---

## What it does

Four things, in order of how useful I have actually found them:

### 1. Context pruning suggestions  (the main reason this exists)

Looks at which files Claude actually referenced in your recent session turns and flags context that has gone stale or is auto-generated bloat (lock files, etc.). Tells you what to cut.

```
$ python autopilot.py prune

Context pruning suggestions  (estimated savings: 7,800 tokens)

  package-lock.json                  3,200 tok   Auto-generated, safe to skip
  requirements.txt                   2,800 tok   Auto-generated, safe to skip
  old_tests/                         1,800 tok   Not referenced in last 9 turns

Run with --apply to update your .claude config.
```

### 2. Live context fuel gauge

A small terminal dashboard that shows how full your current session’s context window is and what your recent burn rate has been (tokens per minute, averaged over the last few turns).

```
  Fuel  ████████████░░░░░░░░░░░░░░  47%   Recent burn: 612 tok/min

  Turns: 31     Tokens used: 105,400     Remaining: 94,600
```

I deliberately do **not** try to predict an "ETA to limit." Burn rate in Claude Code is far too bursty for an honest prediction (a single large file read changes everything). The dashboard shows you the current state and recent trend; you make the call.

### 3. Cost forecast

A rough monthly spend estimate based on your own past usage, broken out by day of week. Useful for spotting patterns ("oh, my Thursdays cost 3x more than my Sundays") more than for getting an exact number.

```
  Today (est):    $4.20
  This week:      $19.80
  Next 30 days:   $127.40
  Heaviest days:  Monday, Thursday
  Lightest days:  Saturday, Sunday
```

### 4. Anomaly log

Lists past turns that consumed unusually large amounts of tokens (z-score outliers) with simple heuristic guesses at the cause. Useful for catching accidental large file reads or runaway tool-call chains in older sessions.

---

## What it does not do

A few things I considered, prototyped, then cut because they were not honest enough to ship:

- **No "ETA to session limit" prediction.** Bursty workloads make this misleading more often than helpful.
- **No "session DNA fingerprint" or pattern classifier.** Fun visualisation, but the labels were not reliable enough to base decisions on.
- **No "prompt efficiency score."** There is no objective way to grade prompt quality from token counts alone, so any score would be made up.

I would rather ship a small thing that works than a flashy thing that overpromises.

---

## Install

```bash
git clone https://github.com/Dharmik2510/claude-autopilot.git
cd claude-autopilot
pip install -r requirements.txt
```

Requires Python 3.11+ and an existing Claude Code installation (so that `~/.claude/projects/` exists).

---

## Usage

```bash
# Try the demo first (no Claude Code data needed)
python demo.py

# Live dashboard
python autopilot.py dashboard

# Pruning suggestions for the most recent session
python autopilot.py prune
python autopilot.py prune --apply        # actually edit .claude config

# Cost forecast
python autopilot.py forecast

# Past anomalies
python autopilot.py anomalies

# Compact one-line status, refreshed in place (good as a sidebar)
python autopilot.py watch
```

---

## How it works

Claude Code stores every session as JSONL files at `~/.claude/projects/<project-hash>/`. Each line is a conversation turn with token usage metadata. Claude Autopilot:

1. Reads those files (with simple mtime-based caching)
2. Aggregates per-turn token usage and which files Claude referenced via tool calls
3. Uses recency weighting to identify stale context (files that Claude has stopped touching)
4. Flags known auto-generated bloat patterns (lock files, build artefacts) for safe pruning
5. Renders a small Rich-based terminal UI with the current state

There is no machine learning, no LLM calls, no cloud component. It is a few hundred lines of Python that parses local files.

---

## Project layout

```
claude-autopilot/
├── autopilot.py              CLI entry point
├── demo.py                   Walkthrough with simulated data
├── core/
│   ├── session_reader.py     JSONL parser
│   ├── fuel_gauge.py         Token/burn-rate state
│   ├── pruner.py             Stale-context detection
│   ├── forecaster.py         Per-day-of-week cost estimate
│   └── anomaly.py            Z-score outlier detection
├── ui/
│   └── dashboard.py          Rich live TUI
└── requirements.txt
```

---

## Honest limitations

- The pruner only knows about files Claude referenced via tool calls. It does not yet parse `CLAUDE.md` or auto-loaded files in `.claude/settings.json` directly, so it can miss bloat that is loaded but never touched.
- Cost estimates assume Sonnet pricing as of early 2025. Update `INPUT_COST_PER_MILLION` / `OUTPUT_COST_PER_MILLION` in `core/forecaster.py` if you use a different model.
- Tested only on macOS and Linux. Windows users probably need WSL.
- `--apply` for pruning rewrites your `.claude/settings.json`. Back it up first if you have custom config.

---

## Contributing

PRs and issues welcome, especially for:

- Better pruning heuristics (parsing `CLAUDE.md`, auto-loaded files)
- Multi-model pricing support
- Windows compatibility

---

## License

MIT (c) [Dharmik Soni](https://github.com/Dharmik2510)
