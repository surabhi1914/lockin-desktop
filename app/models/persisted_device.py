"""Typed device row used by portable synchronization."""

from dataclasses import dataclass
from sqlite3 import Row


@dataclass(frozen=True, slots=True)
class PersistedDevice:
    device_id: str
    device_label: str | None
    created_at_utc: str
    updated_at_utc: str

    @classmethod
    def from_row(cls, row: Row) -> "PersistedDevice":
        return cls(
            device_id=str(row["device_id"]),
            device_label=None if row["device_label"] is None else str(row["device_label"]),
            created_at_utc=str(row["created_at_utc"]),
            updated_at_utc=str(row["updated_at_utc"]),
        )
