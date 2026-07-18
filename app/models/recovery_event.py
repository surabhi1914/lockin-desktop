"""Immutable recovery audit row."""

from dataclasses import dataclass
from sqlite3 import Row


@dataclass(frozen=True, slots=True)
class RecoveryEvent:
    recovery_event_id: str
    session_id: str
    detected_at_utc: str
    event_type: str
    last_heartbeat_at_utc: str | None
    confirmed_boundary_at_utc: str
    unknown_gap_seconds: int
    selected_action: str | None
    finalized_at_utc: str | None
    original_timer_state: str
    integrity_result: str
    created_at_utc: str
    updated_at_utc: str

    @classmethod
    def from_row(cls, row: Row) -> "RecoveryEvent":
        return cls(**dict(row))
