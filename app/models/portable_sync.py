"""Typed portable rows and synchronization reports."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PortableRow:
    entity: str
    record_type: str
    record_id: str
    checksum: str
    local_date: str | None
    values: dict[str, str]
    sort_key: tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class SyncCounts:
    devices: int = 0
    sessions: int = 0
    segments: int = 0
    distractions: int = 0
    skipped: int = 0
    repaired: int = 0
    errors: int = 0


@dataclass(frozen=True, slots=True)
class PortableSyncResult:
    success: bool
    counts: SyncCounts
    touched_files: tuple[Path, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    completed_at_utc: str

    @property
    def message(self) -> str:
        if self.success:
            return "Saved locally and synced"
        return "Saved locally; portable sync pending"


@dataclass(frozen=True, slots=True)
class PortableVerificationReport:
    healthy: bool
    pending: int
    stale: int
    errors: tuple[str, ...]
    checked_files: tuple[Path, ...]
