"""Ordered immutable headers for every portable CSV entity."""

from types import MappingProxyType
from typing import Final

DEVICES_HEADER: Final = (
    "schema_version",
    "device_id",
    "device_label",
    "created_at_utc",
    "updated_at_utc",
)
CATEGORIES_HEADER: Final = (
    "schema_version",
    "category_id",
    "category_name",
    "category_icon",
    "is_active",
    "created_at_utc",
    "updated_at_utc",
)
QUOTES_HEADER: Final = (
    "quote_id",
    "quote_text",
    "author",
    "category",
    "is_active",
    "is_favorite",
)
DAILY_GOALS_HEADER: Final = (
    "schema_version",
    "goal_id",
    "effective_from_date",
    "effective_to_date",
    "goal_seconds",
    "created_at_utc",
    "updated_at_utc",
)
SESSIONS_HEADER: Final = (
    "schema_version",
    "session_id",
    "device_id",
    "session_sequence",
    "category_id",
    "category_name_snapshot",
    "local_date_started",
    "timezone_name",
    "utc_offset_started_minutes",
    "started_at_utc",
    "started_at_local",
    "ended_at_utc",
    "ended_at_local",
    "planned_focus_seconds",
    "actual_focus_seconds",
    "planned_focus_completed_seconds",
    "overtime_seconds",
    "total_pause_seconds",
    "wall_clock_seconds",
    "continuous_block_count",
    "longest_continuous_seconds",
    "average_continuous_seconds",
    "median_continuous_seconds",
    "pause_count",
    "short_pause_count",
    "long_pause_count",
    "distraction_count",
    "status",
    "completion_reason",
    "stopped_early_seconds",
    "completed_planned_timer",
    "overtime_enabled",
    "fullscreen_used",
    "quotes_enabled",
    "start_ritual_enabled",
    "created_at_utc",
    "updated_at_utc",
    "exported_at_utc",
    "record_checksum",
)
SEGMENTS_HEADER: Final = (
    "schema_version",
    "segment_id",
    "source_segment_id",
    "session_id",
    "device_id",
    "segment_sequence",
    "midnight_part_number",
    "segment_type",
    "started_at_utc",
    "ended_at_utc",
    "started_at_local",
    "ended_at_local",
    "local_date",
    "timezone_name",
    "utc_offset_minutes",
    "duration_seconds",
    "counts_as_focus",
    "pause_duration_seconds",
    "pause_classification",
    "breaks_continuity",
    "continuity_group_id",
    "pause_grace_threshold_seconds",
    "focus_phase",
    "crossed_midnight",
    "end_reason",
    "created_at_utc",
    "exported_at_utc",
    "record_checksum",
)
DISTRACTIONS_HEADER: Final = (
    "schema_version",
    "distraction_id",
    "session_id",
    "segment_id",
    "device_id",
    "marked_at_utc",
    "marked_at_local",
    "local_date",
    "timezone_name",
    "category_id",
    "category_name_snapshot",
    "elapsed_focus_seconds",
    "remaining_planned_seconds",
    "is_overtime",
    "optional_note",
    "created_at_utc",
    "exported_at_utc",
    "record_checksum",
)

CSV_CONTRACTS: Final = MappingProxyType(
    {
        "devices": DEVICES_HEADER,
        "categories": CATEGORIES_HEADER,
        "quotes": QUOTES_HEADER,
        "daily_goals": DAILY_GOALS_HEADER,
        "sessions": SESSIONS_HEADER,
        "segments": SEGMENTS_HEADER,
        "distractions": DISTRACTIONS_HEADER,
    }
)


def header_for(entity: str) -> tuple[str, ...]:
    try:
        return CSV_CONTRACTS[entity]
    except KeyError as exc:
        raise ValueError(f"Unknown portable entity: {entity!r}") from exc
