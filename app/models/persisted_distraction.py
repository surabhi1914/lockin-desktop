"""Typed persisted distraction marker."""

from dataclasses import dataclass
from sqlite3 import Row


@dataclass(frozen=True, slots=True)
class PersistedDistraction:
    distraction_id: str
    schema_version: int
    session_id: str
    segment_id: str | None
    device_id: str
    marked_at_utc: str
    marked_at_local: str
    local_date: str
    timezone_name: str
    category_id: str
    category_name_snapshot: str
    elapsed_focus_seconds: int
    remaining_planned_seconds: int
    is_overtime: bool
    optional_note: str | None
    created_at_utc: str

    @classmethod
    def from_row(cls, row: Row) -> "PersistedDistraction":
        values = dict(row)
        values["is_overtime"] = bool(values["is_overtime"])
        return cls(**values)
