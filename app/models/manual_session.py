"""Domain models for finalized focus sessions entered after they occurred."""

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum

from app.models.session_summary import SessionSummary


class ManualSessionResult(StrEnum):
    COMPLETED = "completed"
    COMPLETED_WITH_OVERTIME = "completed_with_overtime"
    STOPPED_EARLY = "stopped_early"


class OverlapKind(StrEnum):
    NONE = "none"
    PARTIAL = "partial"
    FULL = "full"
    DUPLICATE = "duplicate"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class CreateManualSessionCommand:
    local_date: date
    start_time: time
    actual_minutes: int
    planned_minutes: int
    category_id: str
    timezone_name: str
    fold: int | None = None
    overlap_confirmed: bool = False


@dataclass(frozen=True, slots=True)
class ResolvedManualSession:
    command: CreateManualSessionCommand
    started_at: datetime
    ended_at: datetime

    @property
    def actual_seconds(self) -> int:
        return self.command.actual_minutes * 60

    @property
    def planned_seconds(self) -> int:
        return self.command.planned_minutes * 60

    @property
    def result(self) -> ManualSessionResult:
        if self.actual_seconds == self.planned_seconds:
            return ManualSessionResult.COMPLETED
        if self.actual_seconds > self.planned_seconds:
            return ManualSessionResult.COMPLETED_WITH_OVERTIME
        return ManualSessionResult.STOPPED_EARLY


@dataclass(frozen=True, slots=True)
class SessionOverlap:
    kind: OverlapKind
    session_ids: tuple[str, ...] = ()

    @property
    def requires_confirmation(self) -> bool:
        return self.kind in {OverlapKind.PARTIAL, OverlapKind.FULL}

    @property
    def blocked(self) -> bool:
        return self.kind in {OverlapKind.DUPLICATE, OverlapKind.UNRESOLVED}


@dataclass(frozen=True, slots=True)
class ManualSessionCreationResult:
    summary: SessionSummary
    portable_synced: bool
    message: str
