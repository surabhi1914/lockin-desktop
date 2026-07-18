"""Heartbeat-backed unresolved session state."""

from dataclasses import dataclass
from sqlite3 import Row


@dataclass(frozen=True, slots=True)
class RuntimeSessionState:
    session_id: str
    timer_state: str
    temporary_intention_text: None
    remaining_planned_seconds: int
    is_overtime: bool
    last_heartbeat_at_utc: str | None
    updated_at_utc: str
    timer_version: int
    confirmed_planned_focus_seconds: int
    confirmed_overtime_seconds: int
    confirmed_pause_seconds: int
    confirmed_wall_clock_seconds: int
    sleep_started_at_utc: str | None

    @classmethod
    def from_row(cls, row: Row) -> "RuntimeSessionState":
        values = dict(row)
        values["is_overtime"] = bool(values["is_overtime"])
        values["temporary_intention_text"] = None
        return cls(**values)
