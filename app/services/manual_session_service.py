"""Validated, transactional creation of finalized manual focus sessions."""

import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.core.ids import new_uuid4
from app.core.time_utils import (
    format_local,
    format_utc,
    get_timezone,
    split_at_local_midnights,
)
from app.core.wall_clock import SystemWallClock, WallClock, require_utc
from app.database.repositories.category_repository import CategoryRepository
from app.database.repositories.segment_repository import SegmentRepository
from app.database.repositories.session_repository import SessionRepository
from app.database.unit_of_work import UnitOfWork
from app.models.category import Category
from app.models.errors import CategoryNotFoundError
from app.models.manual_session import (
    CreateManualSessionCommand,
    ManualSessionCreationResult,
    OverlapKind,
    ResolvedManualSession,
)
from app.models.manual_session_errors import (
    ManualSessionOverlapError,
    ManualSessionPersistenceError,
    ManualSessionValidationError,
)
from app.models.session_summary import SessionSummary
from app.services.session_checksum_service import session_checksum
from app.services.session_overlap_service import SessionOverlapService

PostCreateSync = Callable[[str], tuple[bool, str]]
FailureInjector = Callable[[str], None]


class ManualSessionService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        device_id: str,
        *,
        post_create_sync: PostCreateSync | None = None,
        wall_clock: WallClock | None = None,
        uuid_provider: Callable[[], str] = new_uuid4,
        failure_injector: FailureInjector | None = None,
    ) -> None:
        self._connection = connection
        self._device_id = device_id
        self._sync = post_create_sync
        self._clock = wall_clock or SystemWallClock()
        self._uuid = uuid_provider
        self._inject = failure_injector or (lambda _point: None)
        self._sessions = SessionRepository(connection)
        self._segments = SegmentRepository(connection)
        self._categories = CategoryRepository(connection)
        self._overlaps = SessionOverlapService(connection)

    def categories(self) -> tuple[Category, ...]:
        return self._categories.list_all()

    def resolve(self, command: CreateManualSessionCommand) -> ResolvedManualSession:
        self._validate_scalar_fields(command)
        zone = get_timezone(command.timezone_name)
        naive = datetime.combine(command.local_date, command.start_time.replace(tzinfo=None))
        candidates = tuple(
            candidate
            for fold in (0, 1)
            if self._round_trips(candidate := naive.replace(tzinfo=zone, fold=fold), naive)
        )
        if not candidates:
            raise ManualSessionValidationError(
                "The selected start time does not exist because the clock moves forward."
            )
        ambiguous = len(candidates) == 2 and candidates[0].utcoffset() != candidates[1].utcoffset()
        if ambiguous and command.fold not in (0, 1):
            raise ManualSessionValidationError(
                "This start time occurs twice. Choose the first or second occurrence."
            )
        if command.fold not in (None, 0, 1):
            raise ManualSessionValidationError("DST occurrence must be first or second.")
        started = candidates[command.fold or 0] if ambiguous else candidates[0]
        now = require_utc(self._clock.now_utc())
        if started.astimezone(UTC) > now:
            raise ManualSessionValidationError("A past session cannot start in the future.")
        ended_utc = started.astimezone(UTC) + timedelta(minutes=command.actual_minutes)
        ended = ended_utc.astimezone(zone)
        parts = split_at_local_midnights(started.astimezone(UTC), ended_utc, command.timezone_name)
        if len(parts) > 2:
            raise ManualSessionValidationError(
                "A manual session cannot cross more than one local midnight."
            )
        return ResolvedManualSession(command, started, ended)

    def overlap_for(self, resolved: ResolvedManualSession) -> object:
        return self._overlaps.assess(
            started_at_utc=resolved.started_at.astimezone(UTC),
            ended_at_utc=resolved.ended_at.astimezone(UTC),
            category_id=resolved.command.category_id,
        )

    def create_manual_session(
        self, command: CreateManualSessionCommand
    ) -> ManualSessionCreationResult:
        resolved = self.resolve(command)
        try:
            category = self._categories.get_by_id(command.category_id)
        except CategoryNotFoundError as exc:
            raise ManualSessionValidationError("The selected category no longer exists.") from exc
        overlap = self._overlaps.assess(
            started_at_utc=resolved.started_at.astimezone(UTC),
            ended_at_utc=resolved.ended_at.astimezone(UTC),
            category_id=command.category_id,
        )
        if overlap.kind is OverlapKind.DUPLICATE:
            raise ManualSessionOverlapError(
                "A session with the same time and category already exists.", overlap
            )
        if overlap.kind is OverlapKind.UNRESOLVED:
            raise ManualSessionOverlapError(
                "Resolve the active or recovery session before adding historical time.",
                overlap,
            )
        if overlap.requires_confirmation and not command.overlap_confirmed:
            label = "fully overlaps" if overlap.kind is OverlapKind.FULL else "overlaps"
            raise ManualSessionOverlapError(
                f"This past session {label} an existing session. Confirm to save it anyway.",
                overlap,
            )
        timestamp = format_utc(require_utc(self._clock.now_utc()))
        session_id = self._uuid()
        try:
            with UnitOfWork(self._connection):
                sequence = self._sessions.allocate_sequence(self._device_id)
                self._sessions.insert(
                    self._session_values(
                        resolved,
                        session_id=session_id,
                        sequence=sequence,
                        category_id=category.category_id,
                        category_name=category.category_name,
                        timestamp=timestamp,
                    )
                )
                self._inject("after_session_insert")
                self._insert_segments(resolved, session_id, timestamp)
                self._inject("after_segments_insert")
                session = self._sessions.get(session_id)
                if session is None:
                    raise ManualSessionPersistenceError("Manual session insert was not visible.")
                self._sessions.update(session_id, {"record_checksum": session_checksum(session)})
        except ManualSessionPersistenceError:
            raise
        except (sqlite3.Error, LookupError, RuntimeError, ValueError) as exc:
            raise ManualSessionPersistenceError(
                "The past session could not be saved; no partial record was kept."
            ) from exc
        session = self._sessions.get(session_id)
        if session is None:
            raise ManualSessionPersistenceError("The saved past session could not be reloaded.")
        summary = SessionSummary.from_session(session)
        try:
            synced, message = (
                self._sync(session_id)
                if self._sync is not None
                else (False, "Past session saved locally; portable sync pending.")
            )
        except (OSError, RuntimeError, ValueError, sqlite3.Error):
            synced, message = False, "Past session saved locally; portable sync pending."
        if not synced:
            message = "Past session saved locally; portable sync pending."
        summary = replace(summary, portable_synced=synced, sync_message=message)
        return ManualSessionCreationResult(summary, synced, message)

    @staticmethod
    def _validate_scalar_fields(command: CreateManualSessionCommand) -> None:
        for value, label in (
            (command.actual_minutes, "Actual focus duration"),
            (command.planned_minutes, "Planned duration"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 1440:
                raise ManualSessionValidationError(f"{label} must be from 1 minute to 24 hours.")
        if not command.category_id.strip():
            raise ManualSessionValidationError("Category is required.")
        if command.start_time.tzinfo is not None:
            raise ManualSessionValidationError(
                "Start time must be a local wall time without an embedded timezone."
            )

    @staticmethod
    def _round_trips(candidate: datetime, naive: datetime) -> bool:
        return candidate.astimezone(UTC).astimezone(candidate.tzinfo).replace(tzinfo=None) == naive

    def _session_values(
        self,
        resolved: ResolvedManualSession,
        *,
        session_id: str,
        sequence: int,
        category_id: str,
        category_name: str,
        timestamp: str,
    ) -> dict[str, object]:
        actual = resolved.actual_seconds
        planned = resolved.planned_seconds
        offset = resolved.started_at.utcoffset()
        if offset is None:
            raise ManualSessionValidationError("The selected timezone has no UTC offset.")
        return {
            "session_id": session_id,
            "schema_version": 2,
            "device_id": self._device_id,
            "session_sequence": sequence,
            "category_id": category_id,
            "category_name_snapshot": category_name,
            "local_date_started": resolved.started_at.date().isoformat(),
            "timezone_name": resolved.command.timezone_name,
            "utc_offset_started_minutes": int(offset.total_seconds() // 60),
            "started_at_utc": format_utc(resolved.started_at),
            "started_at_local": format_local(resolved.started_at),
            "ended_at_utc": format_utc(resolved.ended_at),
            "ended_at_local": format_local(resolved.ended_at),
            "planned_focus_seconds": planned,
            "actual_focus_seconds": actual,
            "planned_focus_completed_seconds": min(actual, planned),
            "overtime_seconds": max(actual - planned, 0),
            "total_pause_seconds": 0,
            "wall_clock_seconds": actual,
            "continuous_block_count": 1,
            "longest_continuous_seconds": actual,
            "average_continuous_seconds": actual,
            "median_continuous_seconds": actual,
            "pause_count": 0,
            "short_pause_count": 0,
            "long_pause_count": 0,
            "distraction_count": 0,
            "status": resolved.result.value,
            "completion_reason": "manual_entry",
            "stopped_early_seconds": max(planned - actual, 0),
            "completed_planned_timer": int(actual >= planned),
            "overtime_enabled": int(actual > planned),
            "fullscreen_used": 0,
            "quotes_enabled": 0,
            "start_ritual_enabled": 0,
            "created_at_utc": timestamp,
            "updated_at_utc": timestamp,
            "entry_source": "manual",
            "manual_entry_created_at_utc": timestamp,
            "manual_entry_updated_at_utc": None,
            "record_checksum": None,
        }

    def _insert_segments(
        self, resolved: ResolvedManualSession, session_id: str, timestamp: str
    ) -> None:
        group_id = self._uuid()
        planned_duration = min(resolved.actual_seconds, resolved.planned_seconds)
        durations = [(planned_duration, "planned")]
        if resolved.actual_seconds > resolved.planned_seconds:
            durations.append((resolved.actual_seconds - resolved.planned_seconds, "overtime"))
        cursor = resolved.started_at.astimezone(UTC)
        for sequence, (duration, phase) in enumerate(durations, start=1):
            ended = cursor + timedelta(seconds=duration)
            offset = cursor.astimezone(get_timezone(resolved.command.timezone_name)).utcoffset()
            if offset is None:
                raise ManualSessionValidationError("The selected timezone has no UTC offset.")
            self._segments.insert(
                {
                    "segment_id": self._uuid(),
                    "schema_version": 2,
                    "session_id": session_id,
                    "device_id": self._device_id,
                    "segment_sequence": sequence,
                    "segment_type": "focus",
                    "started_at_utc": format_utc(cursor),
                    "ended_at_utc": format_utc(ended),
                    "timezone_name": resolved.command.timezone_name,
                    "utc_offset_started_minutes": int(offset.total_seconds() // 60),
                    "duration_seconds": duration,
                    "counts_as_focus": 1,
                    "pause_classification": "none",
                    "breaks_continuity": 0,
                    "continuity_group_id": group_id,
                    "pause_grace_threshold_seconds": 10,
                    "focus_phase": phase,
                    "end_reason": "manual_entry",
                    "created_at_utc": timestamp,
                    "updated_at_utc": timestamp,
                }
            )
            cursor = ended
