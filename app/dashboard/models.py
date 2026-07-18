"""Immutable motivational dashboard result."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    local_date: str
    today_focus_seconds: int
    today_goal_seconds: int | None
    today_progress_ratio: float | None
    yesterday_focus_seconds: int
    current_week_seconds: int
    prior_week_same_point_seconds: int
    today_longest_block_seconds: int
    personal_longest_block_seconds: int
    goal_streak_days: int
    motivation_message: str
    has_focus_history: bool
