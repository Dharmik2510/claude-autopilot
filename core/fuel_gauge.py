"""
fuel_gauge.py - Token consumption tracker for Claude Code sessions

Tracks current token usage against the session context window and computes
a smoothed burn rate (tokens per minute) using a simple moving average.

Note: We deliberately avoid claiming to predict an "ETA to limit." Real burn
rates in Claude Code are extremely bursty (a single large file read can
change everything), so any ETA prediction would be misleading. Instead we
show current state honestly and let the user make their own call.
"""

from dataclasses import dataclass
from typing import List

from core.session_reader import ClaudeSession

SESSION_LIMIT = 200_000  # Default Claude Code context window


@dataclass
class FuelState:
    fuel_percent: float         # Remaining capacity (0-100)
    tokens_used: int            # Tokens consumed so far
    tokens_remaining: int       # Tokens left before context limit
    recent_burn_rate: float     # Tokens per minute over the last few turns
    session_limit: int          # Context window limit
    turn_count: int

    @property
    def is_critical(self) -> bool:
        return self.fuel_percent < 15

    @property
    def is_warning(self) -> bool:
        return self.fuel_percent < 35


class FuelGauge:
    """
    Tracks token consumption state and recent burn rate.

    Burn rate is computed as a simple moving average over the last N turns,
    using real wall-clock time when timestamps are available. This is meant
    to be a descriptive signal ("you have been burning ~600 tok/min recently"),
    not a predictive one.
    """

    def __init__(self, session_limit: int = SESSION_LIMIT, window_size: int = 5):
        self.session_limit = session_limit
        self.window_size = window_size

    def compute(self, session: ClaudeSession) -> FuelState:
        cumulative = session.cumulative_tokens()
        tokens_used = cumulative[-1] if cumulative else 0
        tokens_remaining = max(0, self.session_limit - tokens_used)
        fuel_percent = 100.0 * tokens_remaining / self.session_limit
        burn_rate = self._recent_burn_rate(session)

        return FuelState(
            fuel_percent=fuel_percent,
            tokens_used=tokens_used,
            tokens_remaining=tokens_remaining,
            recent_burn_rate=burn_rate,
            session_limit=self.session_limit,
            turn_count=session.turn_count,
        )

    def _recent_burn_rate(self, session: ClaudeSession) -> float:
        """
        Compute average tokens per minute over the most recent N turns,
        using real timestamps when available.
        """
        turns = session.turns[-self.window_size:]
        if len(turns) < 2:
            return 0.0

        try:
            total_tokens = sum(t.total_tokens for t in turns[1:])
            span_minutes = (turns[-1].timestamp - turns[0].timestamp).total_seconds() / 60.0
            if span_minutes <= 0.01:
                return 0.0
            return total_tokens / span_minutes
        except Exception:
            return 0.0


def render_fuel_bar(state: FuelState, width: int = 30) -> str:
    """Render a simple text fuel bar for terminal display."""
    filled = max(0, min(width, int(width * state.fuel_percent / 100)))
    bar = chr(0x2588) * filled + chr(0x2591) * (width - filled)
    return f"{bar}  {state.fuel_percent:.0f}%  Recent burn: {state.recent_burn_rate:.0f} tok/min"
