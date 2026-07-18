"""Typed SQLite timer segment record."""

from dataclasses import dataclass
from sqlite3 import Row


@dataclass(frozen=True, slots=True)
class PersistedSegment:
    segment_id: str
    schema_version: int
    session_id: str
    device_id: str
    segment_sequence: int
    segment_type: str
    started_at_utc: str
    ended_at_utc: str | None
    timezone_name: str
    utc_offset_started_minutes: int
    duration_seconds: int
    counts_as_focus: bool
    pause_classification: str
    breaks_continuity: bool
    continuity_group_id: str | None
    pause_grace_threshold_seconds: int
    focus_phase: str
    end_reason: str | None
    created_at_utc: str
    updated_at_utc: str

    @classmethod
    def from_row(cls, row: Row) -> "PersistedSegment":
        values = dict(row)
        values["counts_as_focus"] = bool(values["counts_as_focus"])
        values["breaks_continuity"] = bool(values["breaks_continuity"])
        return cls(**values)
