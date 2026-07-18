"""Local bookkeeping entry for one verified portable row."""

from dataclasses import dataclass
from sqlite3 import Row


@dataclass(frozen=True, slots=True)
class SyncLedgerEntry:
    record_type: str
    record_id: str
    partition_relative_path: str
    record_checksum: str
    exported_at_utc: str

    @classmethod
    def from_row(cls, row: Row) -> "SyncLedgerEntry":
        return cls(**dict(row))
