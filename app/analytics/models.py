"""Immutable filters and complete statistics result models."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnalyticsFilters:
    from_date: str
    to_date: str
    category_ids: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    device_ids: tuple[str, ...] = ()
    include_overtime: bool = True
    include_recovered: bool = True
    minimum_focus_seconds: int = 0


@dataclass(frozen=True, slots=True)
class DailyMetric:
    local_date: str
    focus_seconds: int
    goal_seconds: int
    session_count: int
    longest_block_seconds: int
    pause_seconds: int
    distraction_count: int


@dataclass(frozen=True, slots=True)
class CategoryMetric:
    category_id: str
    category_name: str
    focus_seconds: int
    session_count: int
    average_block_seconds: int
    overtime_seconds: int


@dataclass(frozen=True, slots=True)
class DeviceMetric:
    device_id: str
    device_label: str
    focus_seconds: int
    session_count: int
    is_current_device: bool


@dataclass(frozen=True, slots=True)
class StatisticsResult:
    filters: AnalyticsFilters
    daily: tuple[DailyMetric, ...]
    total_focus_seconds: int
    average_focus_per_active_day_seconds: int
    median_focus_per_active_day_seconds: int
    active_days: int
    goal_met_days: int
    best_day: tuple[str, int] | None
    best_week: tuple[str, int] | None
    best_month: tuple[str, int] | None
    session_count: int
    sessions_by_status: tuple[tuple[str, int], ...]
    completion_rate: float | None
    planned_seconds: int
    planned_completed_seconds: int
    planned_completion_percentage: float | None
    stopped_early_seconds: int
    overtime_seconds: int
    actual_planned_ratio: float | None
    block_count: int
    longest_block_seconds: int
    average_block_seconds: int
    median_block_seconds: int
    block_buckets: tuple[tuple[str, int], ...]
    total_pause_seconds: int
    pause_count: int
    short_pause_count: int
    long_pause_count: int
    system_sleep_pause_count: int
    average_pause_seconds: int
    pause_to_focus_ratio: float | None
    distraction_count: int
    distractions_per_focus_hour: float | None
    sessions_with_distractions: int
    average_distractions_per_marked_session: float | None
    categories: tuple[CategoryMetric, ...]
    devices: tuple[DeviceMetric, ...]
