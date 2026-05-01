"""
anomaly.py - Token Consumption Anomaly Detector

Uses z-score analysis to detect turns where token consumption deviated
significantly from the session baseline. Identifies probable root causes
and generates actionable recommendations.

Why it matters: A single accidental large file read can consume 20% of
your context budget without you realizing it.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, List, Optional

from core.session_reader import ClaudeSession, SessionTurn


@dataclass
class TokenAnomaly:
    turn_number: int
    timestamp: datetime
    actual_tokens: int
    baseline_tokens: float
    z_score: float
    probable_cause: str
    recommendation: str
    severity: str   # "WARNING" | "CRITICAL"


# Root cause heuristics: (condition_fn, cause_label, recommendation)
# Each condition receives (turn, z_score, session)
ROOT_CAUSE_HEURISTICS = [
    (
        lambda t, z, s: t.input_tokens > t.output_tokens * 20,
        "Large file read — input far exceeds output (pure context ingestion)",
        "Use targeted queries instead of full file reads. Ask Claude to search for specific symbols.",
    ),
    (
        lambda t, z, s: t.cache_read_tokens == 0 and t.input_tokens > 5000,
        "Cold context — no cache hit on large input (first reference to many files)",
        "Use /clear to reset and restructure your session. Or warm up cache with /compact.",
    ),
    (
        lambda t, z, s: t.tool_calls > 5,
        "Multi-tool turn — many tool calls triggered large context chain",
        "Break complex requests into focused sub-tasks across multiple turns.",
    ),
    (
        lambda t, z, s: t.input_tokens > 15000,
        "Giant turn — extremely large input (possible repository dump or full file list)",
        "Avoid sending entire codebases. Use --include flags to scope Claude to specific dirs.",
    ),
    (
        lambda t, z, s: True,  # Default fallback
        "Unexpected token spike — cause unclear",
        "Review what files were open and referenced in this turn.",
    ),
]


class AnomalyDetector:
    """
    Scans a session for token anomalies using z-score thresholding.

    Z-score = (turn_tokens - mean_tokens) / std_tokens

    A z-score of 3.0 means a turn used 3 standard deviations more tokens
    than the session average — statistically very unusual.
    """

    DEFAULT_Z_THRESHOLD = 2.5
    MIN_TURNS_FOR_BASELINE = 4

    def __init__(self, z_threshold: float = DEFAULT_Z_THRESHOLD):
        self.z_threshold = z_threshold

    def scan(self, session: ClaudeSession) -> Iterator[TokenAnomaly]:
        deltas = session.token_deltas()
        if len(deltas) < self.MIN_TURNS_FOR_BASELINE:
            return

        mean, std = self._stats(deltas)
        if std == 0:
            return

        for i, (turn, delta) in enumerate(zip(session.turns, deltas)):
            z = (delta - mean) / std
            if z >= self.z_threshold:
                cause, rec, severity = self._classify(turn, z, session)
                yield TokenAnomaly(
                    turn_number=i + 1,
                    timestamp=turn.timestamp,
                    actual_tokens=delta,
                    baseline_tokens=mean,
                    z_score=z,
                    probable_cause=cause,
                    recommendation=rec,
                    severity="CRITICAL" if z > 5.0 else "WARNING",
                )

    def _stats(self, values: List[int]):
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(variance)
        return mean, std

    def _classify(self, turn: SessionTurn, z_score: float, session: ClaudeSession):
        for condition_fn, cause, rec in ROOT_CAUSE_HEURISTICS:
            try:
                if condition_fn(turn, z_score, session):
                    severity = "CRITICAL" if z_score > 5.0 else "WARNING"
                    return cause, rec, severity
            except Exception:
                continue
        return "Unknown cause", "Review this turn manually.", "WARNING"
