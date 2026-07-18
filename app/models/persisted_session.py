"""Typed SQLite session record used by repositories and summaries."""

from dataclasses import dataclass
from sqlite3 import Row


@dataclass(frozen=True, slots=True)
class PersistedSession:
    session_id: str
    schema_version: int
    device_id: str
    session_sequence: int
    category_id: str
    category_name_snapshot: str
    local_date_started: str
    timezone_name: str
    utc_offset_started_minutes: int
    started_at_utc: str
    started_at_local: str
    ended_at_utc: str | None
    ended_at_local: str | None
    planned_focus_seconds: int
    actual_focus_seconds: int
    planned_focus_completed_seconds: int
    overtime_seconds: int
    total_pause_seconds: int
    wall_clock_seconds: int
    continuous_block_count: int
    longest_continuous_seconds: int
    average_continuous_seconds: int
    median_continuous_seconds: int
    pause_count: int
    short_pause_count: int
    long_pause_count: int
    distraction_count: int
    status: str
    completion_reason: str | None
    stopped_early_seconds: int
    completed_planned_timer: bool
    overtime_enabled: bool
    fullscreen_used: bool
    quotes_enabled: bool
    start_ritual_enabled: bool
    created_at_utc: str
    updated_at_utc: str
    record_checksum: str | None

    @classmethod
    def from_row(cls, row: Row) -> "PersistedSession":
        values = dict(row)
        for key in (
            "completed_planned_timer",
            "overtime_enabled",
            "fullscreen_used",
            "quotes_enabled",
            "start_ritual_enabled",
        ):
            values[key] = bool(values[key])
        return cls(**values)


FINAL_SESSION_STATUSES = (
    "completed",
    "completed_with_overtime",
    "stopped_early",
    "recovered",
    "discarded",
)
