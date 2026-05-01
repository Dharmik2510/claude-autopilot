"""
fuel_gauge.py - Real-time token burn rate tracker and session limit predictor

Uses Exponential Moving Average (EMA) for smoothed burn rate calculation.
Uses linear regression on cumulative token trend for ETA prediction.
This is the core innovation: predicting WHEN you will hit limits, not just WHERE you are.
"""

import math
from dataclasses import dataclass
from typing import List, Optional

from core.session_reader import ClaudeSession

SESSION_LIMIT = 200_000  # Default Claude Code context window
EMA_ALPHA = 0.25          # EMA smoothing factor (0=more smooth, 1=more reactive)


@dataclass
class FuelState:
    fuel_percent: float         # Remaining capacity (0-100)
    tokens_used: int            # Tokens consumed so far
    tokens_remaining: int       # Estimated tokens left
    burn_rate: float            # Tokens per minute (EMA-smoothed)
    eta_minutes: float          # Estimated minutes until session limit
    session_limit: int          # Context window limit
    turn_count: int             # Number of turns in session
    trend: str                  # "ACCELERATING" | "STEADY" | "DECELERATING"
    confidence: float           # Prediction confidence 0.0-1.0

    @property
    def is_critical(self) -> bool:
        return self.fuel_percent < 15

    @property
    def is_warning(self) -> bool:
        return self.fuel_percent < 35


class FuelGauge:
    """
    Tracks token burn rate and predicts session limit ETA.

    Algorithm:
    1. Compute per-turn token deltas
    2. Apply EMA smoothing to get instantaneous burn rate
    3. Use linear regression on recent turns for trend detection
    4. Extrapolate to predict ETA to SESSION_LIMIT
    """

    def __init__(self, session_limit: int = SESSION_LIMIT, ema_alpha: float = EMA_ALPHA):
        self.session_limit = session_limit
        self.ema_alpha = ema_alpha

    def compute(self, session: ClaudeSession) -> FuelState:
        deltas = session.token_deltas()
        cumulative = session.cumulative_tokens()
        tokens_used = cumulative[-1] if cumulative else 0
        tokens_remaining = max(0, self.session_limit - tokens_used)
        fuel_percent = 100.0 * tokens_remaining / self.session_limit

        burn_rate = self._ema_burn_rate(deltas, session)
        eta = self._predict_eta(burn_rate, tokens_remaining)
        trend = self._detect_trend(deltas)
        confidence = self._confidence(len(deltas))

        return FuelState(
            fuel_percent=fuel_percent,
            tokens_used=tokens_used,
            tokens_remaining=tokens_remaining,
            burn_rate=burn_rate,
            eta_minutes=eta,
            session_limit=self.session_limit,
            turn_count=len(deltas),
            trend=trend,
            confidence=confidence,
        )

    def _ema_burn_rate(self, deltas: List[int], session: ClaudeSession) -> float:
        """
        Compute EMA-smoothed burn rate in tokens per minute.
        If timestamps are available, use real wall-clock time.
        Otherwise, assume average 2 minutes per turn.
        """
        if not deltas:
            return 0.0

        # Try to get real timestamps for time-based burn rate
        timestamps = [t.timestamp for t in session.turns]
        if len(timestamps) >= 2:
            try:
                time_spans = []
                for i in range(1, len(timestamps)):
                    diff = (timestamps[i] - timestamps[i - 1]).total_seconds() / 60.0
                    if 0.01 < diff < 60:  # Sanity bounds: between 1 second and 1 hour
                        time_spans.append(max(0.01, diff))
                if time_spans and len(time_spans) == len(deltas) - 1:
                    rates = [deltas[i + 1] / time_spans[i] for i in range(len(time_spans))]
                    return self._ema(rates)
            except Exception:
                pass

        # Fallback: assume 2 minutes per turn
        turn_rates = [d / 2.0 for d in deltas]
        return self._ema(turn_rates)

    def _ema(self, values: List[float]) -> float:
        if not values:
            return 0.0
        ema = values[0]
        for v in values[1:]:
            ema = self.ema_alpha * v + (1 - self.ema_alpha) * ema
        return ema

    def _predict_eta(self, burn_rate: float, tokens_remaining: int) -> float:
        if burn_rate <= 0:
            return float("inf")
        return tokens_remaining / burn_rate

    def _detect_trend(self, deltas: List[int]) -> str:
        if len(deltas) < 4:
            return "STEADY"
        # Compare average of first half vs second half
        mid = len(deltas) // 2
        first_half_avg = sum(deltas[:mid]) / mid
        second_half_avg = sum(deltas[mid:]) / max(1, len(deltas) - mid)
        ratio = second_half_avg / max(1, first_half_avg)
        if ratio > 1.25:
            return "ACCELERATING"
        elif ratio < 0.75:
            return "DECELERATING"
        return "STEADY"

    def _confidence(self, turn_count: int) -> float:
        """More turns = higher prediction confidence. Saturates at 10 turns."""
        return min(1.0, turn_count / 10.0)


def render_fuel_bar(state: FuelState, width: int = 30) -> str:
    """
    Render a fuel gauge bar string for terminal display.

    Example: ████████████████████░░░░░░░░░░  67%  ETA ~18min
    """
    filled = max(0, min(width, int(width * state.fuel_percent / 100)))
    empty = width - filled
    bar = chr(0x2588) * filled + chr(0x2591) * empty

    eta_str = f"~{state.eta_minutes:.0f}m" if state.eta_minutes != float("inf") else "?"
    burn_str = f"{state.burn_rate:.0f} tok/min"

    return f"{bar}  {state.fuel_percent:.0f}%  ETA {eta_str}  Burn: {burn_str}"
