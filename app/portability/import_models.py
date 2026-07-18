"""Immutable plans, source records, conflicts, and results for Phase 8 import."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from app.portability.manifest import PortableManifest


class ImportMode(StrEnum):
    FRESH = "fresh"
    MERGE = "merge"
    VERIFY = "verify"


@dataclass(frozen=True, slots=True)
class SourceLocation:
    path: Path
    row_number: int


@dataclass(frozen=True, slots=True)
class PortableSourceRow:
    entity: str
    record_id: str
    values: dict[str, str]
    location: SourceLocation
    checksum: str


@dataclass(frozen=True, slots=True)
class LogicalSegment:
    segment_id: str
    session_id: str
    device_id: str
    values: dict[str, object]
    portable_rows: tuple[PortableSourceRow, ...]


@dataclass(frozen=True, slots=True)
class EntityCounts:
    devices: int = 0
    categories: int = 0
    quotes: int = 0
    goals: int = 0
    sessions: int = 0
    segment_rows: int = 0
    logical_segments: int = 0
    distractions: int = 0


@dataclass(frozen=True, slots=True)
class SourceSummary:
    portable_root: Path
    counts: EntityCounts
    earliest_local_date: str | None
    latest_local_date: str | None
    device_labels: tuple[str, ...]
    file_count: int


@dataclass(frozen=True, slots=True)
class ImportWarning:
    code: str
    message: str
    location: SourceLocation | None = None


@dataclass(frozen=True, slots=True)
class ImportConflict:
    entity: str
    record_id: str
    reason: str
    location: SourceLocation | None
    existing_summary: dict[str, object]
    incoming_summary: dict[str, object]
    allowed_actions: tuple[str, ...] = (
        "abort_import",
        "skip_conflicting_record",
        "export_conflict_report",
    )


@dataclass(frozen=True, slots=True)
class PlannedOperation:
    entity: str
    record_id: str
    action: str


@dataclass(frozen=True, slots=True)
class ImportReadinessReport:
    safe: bool
    summary: SourceSummary | None
    errors: tuple[str, ...] = ()
    warnings: tuple[ImportWarning, ...] = ()
    conflicts: tuple[ImportConflict, ...] = ()
    operations: tuple[PlannedOperation, ...] = ()
    recommended_mode: ImportMode = ImportMode.VERIFY


@dataclass(frozen=True, slots=True)
class ImportPlan:
    mode: ImportMode
    summary: SourceSummary
    operations: tuple[PlannedOperation, ...]
    conflicts: tuple[ImportConflict, ...]
    warnings: tuple[ImportWarning, ...]

    @property
    def inserts(self) -> int:
        return sum(item.action == "insert" for item in self.operations)

    @property
    def skips(self) -> int:
        return sum(item.action == "skip_exact" for item in self.operations)


@dataclass(frozen=True, slots=True)
class PortableImportBundle:
    root: Path
    manifest: PortableManifest
    rows: dict[str, tuple[PortableSourceRow, ...]]
    logical_segments: tuple[LogicalSegment, ...]
    segment_id_map: dict[str, str]
    summary: SourceSummary
    warnings: tuple[ImportWarning, ...]
    file_hashes: dict[str, str]


@dataclass(frozen=True, slots=True)
class ImportResult:
    success: bool
    import_id: str
    mode: ImportMode
    inserted: int = 0
    skipped: int = 0
    conflicts: tuple[ImportConflict, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    backup_path: Path | None = None
    staging_path: Path | None = None
    database_path: Path | None = None
    local_device_id: str | None = None
    conflict_report_path: Path | None = None
    operations: tuple[PlannedOperation, ...] = field(default_factory=tuple)
