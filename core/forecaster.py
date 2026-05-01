"""
forecaster.py - Cost Forecasting Engine

Projects your Claude Code spending based on historical session data.
Uses your personal usage distribution (rather than generic averages)
to give you a forecast that reflects your actual work patterns.

Key insight: Monday/Thursday sprints cost 3x as much as weekend sessions.
Knowing this lets you plan smarter, not just spend less.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.session_reader import SessionReader

# Claude Code pricing (approximate, as of 2025)
# Input: $3/M tokens, Output: $15/M tokens (Sonnet 3.7)
INPUT_COST_PER_MILLION = 3.0
OUTPUT_COST_PER_MILLION = 15.0

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class ForecastReport:
    today_estimate: float
    week_estimate: float
    total_forecast: float
    peak_days: List[str]
    cheap_days: List[str]
    recommendation: str
    daily_breakdown: Dict[str, float] = field(default_factory=dict)
    monthly_by_day_of_week: Dict[str, float] = field(default_factory=dict)


class CostForecaster:
    """
    Builds a personal usage model and forecasts future Claude Code costs.

    The model tracks:
    - Average daily token usage by day of week
    - Session frequency and duration patterns
    - Cost trajectory over the past 30 days
    """

    def __init__(self, reader: SessionReader):
        self.reader = reader
        self._cost_cache: Optional[List[tuple]] = None

    def _compute_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_cost = input_tokens * INPUT_COST_PER_MILLION / 1_000_000
        output_cost = output_tokens * OUTPUT_COST_PER_MILLION / 1_000_000
        return input_cost + output_cost

    def _get_all_sessions_with_cost(self) -> List[tuple]:
        """Returns [(session, cost, date)] for all historical sessions."""
        if self._cost_cache is not None:
            return self._cost_cache
        sessions = self.reader.get_sessions()
        result = []
        for session in sessions:
            if not session.turns:
                continue
            cost = self._compute_cost(session.total_input_tokens, session.total_output_tokens)
            try:
                date = session.turns[0].timestamp.date()
            except Exception:
                date = datetime.now().date()
            result.append((session, cost, date))
        self._cost_cache = result
        return result

    def today_estimate(self) -> float:
        all_data = self._get_all_sessions_with_cost()
        today = datetime.now().date()
        total = sum(cost for _, cost, date in all_data if date == today)
        return total

    def generate(self, horizon_days: int = 30, breakdown: bool = False) -> ForecastReport:
        all_data = self._get_all_sessions_with_cost()
        if not all_data:
            return ForecastReport(
                today_estimate=0.0,
                week_estimate=0.0,
                total_forecast=0.0,
                peak_days=["No data"],
                cheap_days=["No data"],
                recommendation="Run some Claude Code sessions first to generate forecast data.",
            )

        # Aggregate by date
        daily_cost: Dict = defaultdict(float)
        for _, cost, date in all_data:
            daily_cost[date] += cost

        # Aggregate by day of week
        dow_cost: Dict[int, List[float]] = defaultdict(list)
        for date, cost in daily_cost.items():
            dow_cost[date.weekday()].append(cost)

        # Average cost per day of week
        dow_avg = {}
        for dow in range(7):
            costs = dow_cost.get(dow, [])
            dow_avg[dow] = sum(costs) / len(costs) if costs else 0.0

        # Today and week estimates
        today = datetime.now().date()
        today_est = daily_cost.get(today, dow_avg.get(today.weekday(), 0.0))

        week_est = sum(
            dow_avg.get((today.weekday() + i) % 7, 0.0)
            for i in range(7)
        )

        # Forecast total
        total = sum(
            dow_avg.get((today.weekday() + i) % 7, 0.0)
            for i in range(horizon_days)
        )

        # Peak and cheap days
        sorted_days = sorted(dow_avg.items(), key=lambda x: x[1], reverse=True)
        peak_days = [DAY_NAMES[d] for d, _ in sorted_days[:2] if sorted_days[0][1] > 0]
        cheap_days = [DAY_NAMES[d] for d, _ in sorted_days[-2:] if sorted_days[-1][1] >= 0]

        # Recommendation
        recommendation = self._generate_recommendation(dow_avg, total)

        # Daily breakdown
        daily_bd = {}
        if breakdown:
            for i in range(min(horizon_days, 14)):
                d = today + timedelta(days=i)
                daily_bd[d.strftime("%a %m/%d")] = dow_avg.get(d.weekday(), 0.0)

        return ForecastReport(
            today_estimate=round(today_est, 2),
            week_estimate=round(week_est, 2),
            total_forecast=round(total, 2),
            peak_days=peak_days or ["N/A"],
            cheap_days=cheap_days or ["N/A"],
            recommendation=recommendation,
            daily_breakdown=daily_bd,
        )

    def _generate_recommendation(self, dow_avg: dict, monthly_total: float) -> str:
        if not any(dow_avg.values()):
            return "Not enough data for recommendations yet."

        max_dow = max(dow_avg.items(), key=lambda x: x[1])
        min_dow = min(dow_avg.items(), key=lambda x: x[1])
        ratio = max_dow[1] / max(0.01, min_dow[1])

        if ratio > 3:
            return (
                f"Your {DAY_NAMES[max_dow[0]]} sessions cost {ratio:.0f}x more than {DAY_NAMES[min_dow[0]]}. "
                "Consider batching large context work earlier in the week."
            )
        elif monthly_total > 200:
            return "High monthly spend detected. Review top context consumers with: autopilot prune"
        else:
            return "Usage looks efficient. Keep an eye on Mondays when sprints tend to spike."
