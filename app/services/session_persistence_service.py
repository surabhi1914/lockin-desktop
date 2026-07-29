"""Transactional mapping from monotonic timer snapshots to SQLite lifecycle records."""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID, uuid5

from app.core.constants import DATA_SCHEMA_VERSION, DEFAULT_TIMEZONE
from app.core.ids import new_uuid4
from app.core.time_utils import format_local, format_utc, get_timezone
from app.core.wall_clock import SystemWallClock, WallClock, require_utc
from app.database.repositories.distraction_repository import DistractionRepository
from app.database.repositories.runtime_state_repository import RuntimeStateRepository
from app.database.repositories.segment_repository import SegmentRepository
from app.database.repositories.session_repository import SessionRepository
from app.database.unit_of_work import UnitOfWork
from app.models.category import Category
from app.models.distraction_marker import DistractionMarker
from app.models.errors import (
    NoActiveFocusSessionError,
    SessionIntegrityError,
    SessionPersistenceBlockedError,
    SessionPersistenceError,
    SessionWriteConflictError,
    UnfinishedSessionError,
)
from app.models.focus_session_draft import FocusSessionDraft
from app.models.persisted_segment import PersistedSegment
from app.models.session_summary import SessionSummary
from app.services.session_aggregate_service import SessionAggregateService
from app.services.session_checksum_service import session_checksum
from app.timer.enums import TimerState
from app.timer.models import TimerSnapshot

FailureInjector = Callable[[str], None]
PostFinalizeSync = Callable[[str], tuple[bool, str]]


@dataclass(slots=True)
class PersistenceContext:
    session_id: str
    device_id: str
    session_sequence: int
    category_id: str
    category_name: str
    timezone_name: str
    continuity_group_id: str
    completion_wall_elapsed_ns: int | None = None
    pause_started_total_ns: int | None = None


class SessionPersistenceService:
    """Serialize complete lifecycle transactions on one SQLite connection.

    The timer starts immediately before ``start_session``. Its monotonic start is
    the duration boundary; wall timestamps are metadata captured inside the
    successful start transaction. A failed start is discarded by the caller.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        device_id: str,
        *,
        wall_clock: WallClock | None = None,
        timezone_name: str = DEFAULT_TIMEZONE,
        uuid_provider: Callable[[], str] = new_uuid4,
        failure_injector: FailureInjector | None = None,
        post_finalize_sync: PostFinalizeSync | None = None,
    ) -> None:
        self._connection = connection
        self._device_id = device_id
        self._clock = wall_clock or SystemWallClock()
        self._timezone_name = timezone_name
        self._uuid = uuid_provider
        self._inject = failure_injector or (lambda _point: None)
        self._post_finalize_sync = post_finalize_sync
        self._uow = UnitOfWork(connection)
        self.sessions = SessionRepository(connection)
        self.segments = SegmentRepository(connection)
        self.distractions = DistractionRepository(connection)
        self.runtime = RuntimeStateRepository(connection)
        self.aggregates = SessionAggregateService(self.sessions)
        self._context: PersistenceContext | None = None
        self._busy = False
        self._blocked_reason: str | None = None

    @property
    def active_context(self) -> PersistenceContext | None:
        return self._context

    @property
    def blocked_reason(self) -> str | None:
        return self._blocked_reason

    def block_new_sessions(self, reason: str) -> None:
        self._blocked_reason = reason

    def clear_block(self) -> None:
        self._blocked_reason = None

    def start_session(
        self,
        draft: FocusSessionDraft,
        category: Category,
        snapshot: TimerSnapshot,
    ) -> PersistenceContext:
        if self._blocked_reason:
            raise UnfinishedSessionError(self._blocked_reason)
        if self._context is not None:
            raise SessionWriteConflictError("a persisted session is already active")
        timestamp, local = self._stamp()
        session_id = self._uuid()
        group_id = self._uuid()
        segment_id = self._uuid()
        try:
            with self._transaction():
                sequence = self.sessions.allocate_sequence(self._device_id)
                self.sessions.insert(
                    {
                        "session_id": session_id,
                        "schema_version": DATA_SCHEMA_VERSION,
                        "device_id": self._device_id,
                        "session_sequence": sequence,
                        "category_id": category.category_id,
                        "category_name_snapshot": category.category_name,
                        "local_date_started": local.date().isoformat(),
                        "timezone_name": self._timezone_name,
                        "utc_offset_started_minutes": self._offset_minutes(local),
                        "started_at_utc": format_utc(timestamp),
                        "started_at_local": format_local(local),
                        "planned_focus_seconds": draft.planned_duration_seconds,
                        "status": "running",
                        "overtime_enabled": int(draft.overtime_enabled),
                        "fullscreen_used": int(draft.start_in_fullscreen),
                        "quotes_enabled": int(draft.show_quotes),
                        "start_ritual_enabled": int(draft.start_ritual_enabled),
                        "created_at_utc": format_utc(timestamp),
                        "updated_at_utc": format_utc(timestamp),
                        "entry_source": "timer",
                    }
                )
                self._insert_segment(
                    segment_id,
                    session_id,
                    1,
                    "focus",
                    "planned",
                    group_id,
                    timestamp,
                    local,
                    draft.pause_grace_seconds,
                )
                self.runtime.insert(
                    {
                        "session_id": session_id,
                        "timer_state": snapshot.state.value,
                        "temporary_intention_text": None,
                        "remaining_planned_seconds": snapshot.remaining_planned_seconds,
                        "is_overtime": 0,
                        "last_heartbeat_at_utc": format_utc(timestamp),
                        "updated_at_utc": format_utc(timestamp),
                        "timer_version": snapshot.version,
                        "confirmed_planned_focus_seconds": snapshot.planned_focus_seconds,
                        "confirmed_overtime_seconds": snapshot.overtime_seconds,
                        "confirmed_pause_seconds": snapshot.total_pause_seconds,
                        "confirmed_wall_clock_seconds": snapshot.wall_elapsed_seconds,
                        "sleep_started_at_utc": None,
                    }
                )
                self._inject("start_before_commit")
        except (sqlite3.Error, LookupError, RuntimeError) as exc:
            raise SessionPersistenceError(f"could not save session start: {exc}") from exc
        self._context = PersistenceContext(
            session_id,
            self._device_id,
            sequence,
            category.category_id,
            category.category_name,
            self._timezone_name,
            group_id,
        )
        return self._context

    def pause(self, snapshot: TimerSnapshot) -> None:
        context = self._require_context()
        timestamp, local = self._stamp()
        try:
            with self._transaction(diverged=True):
                self._close_open(context, snapshot, timestamp, "paused")
                self._open_next(context, "pause", "not_applicable", timestamp, local, snapshot)
                self._sync_session(context.session_id, snapshot, "paused", timestamp)
                self._sync_runtime(context.session_id, snapshot, timestamp, force=True)
                self._inject("pause_before_commit")
        except SessionPersistenceError:
            raise
        context.pause_started_total_ns = snapshot.total_pause_ns

    def resume(self, snapshot: TimerSnapshot) -> None:
        context = self._require_context()
        open_segment = self._require_open(context.session_id, "pause")
        started_ns = context.pause_started_total_ns
        if started_ns is None:
            raise SessionIntegrityError("pause monotonic boundary is missing")
        pause_duration_ns = snapshot.total_pause_ns - started_ns
        system_sleep = open_segment.pause_classification == "system_sleep"
        short = (
            not system_sleep and pause_duration_ns <= snapshot.pause_grace_seconds * 1_000_000_000
        )
        timestamp, local = self._stamp()
        phase = "overtime" if snapshot.state is TimerState.OVERTIME else "planned"
        next_group = context.continuity_group_id if short else self._uuid()
        try:
            with self._transaction(diverged=True):
                duration = self._segment_duration(
                    context.session_id,
                    open_segment.segment_type,
                    open_segment.focus_phase,
                    snapshot,
                )
                self.segments.close(
                    open_segment.segment_id,
                    {
                        "ended_at_utc": format_utc(timestamp),
                        "duration_seconds": duration,
                        "pause_classification": (
                            "system_sleep"
                            if system_sleep
                            else "short_grace_pause"
                            if short
                            else "continuity_break"
                        ),
                        "breaks_continuity": int(not short),
                        "continuity_group_id": next_group,
                        "end_reason": "resumed",
                        "updated_at_utc": format_utc(timestamp),
                    },
                )
                self._open_next(
                    context,
                    "focus",
                    phase,
                    timestamp,
                    local,
                    snapshot,
                    group_id=next_group,
                )
                self._sync_session(context.session_id, snapshot, "running", timestamp)
                self._sync_runtime(context.session_id, snapshot, timestamp, force=True)
                self._inject("resume_before_commit")
        except SessionPersistenceError:
            raise
        except (sqlite3.Error, LookupError, RuntimeError) as exc:
            self._mark_diverged(exc)
        context.continuity_group_id = next_group
        context.pause_started_total_ns = None

    def system_sleep_pause(self, snapshot: TimerSnapshot) -> None:
        """Persist an already-synchronized engine pause as a continuity break."""
        context = self._require_context()
        timestamp, local = self._stamp()
        try:
            with self._transaction(diverged=True):
                open_segment = self.segments.open_for_session(context.session_id)
                if open_segment is None:
                    raise SessionIntegrityError("sleep transition has no open segment")
                if open_segment.segment_type == "focus":
                    self._close_open(context, snapshot, timestamp, "system_sleep")
                    self._open_next(
                        context,
                        "pause",
                        "not_applicable",
                        timestamp,
                        local,
                        snapshot,
                    )
                    open_segment = self._require_open(context.session_id, "pause")
                    context.pause_started_total_ns = snapshot.total_pause_ns
                self.segments.update_open(
                    open_segment.segment_id,
                    {
                        "pause_classification": "system_sleep",
                        "breaks_continuity": 1,
                        "updated_at_utc": format_utc(timestamp),
                    },
                )
                self._sync_session(context.session_id, snapshot, "paused", timestamp)
                self._sync_runtime(
                    context.session_id,
                    snapshot,
                    timestamp,
                    force=True,
                    sleep_started_at_utc=format_utc(timestamp),
                )
                self._inject("sleep_pause_before_commit")
        except SessionPersistenceError:
            raise

    def planned_completed(self, snapshot: TimerSnapshot) -> bool:
        context = self._require_context()
        if context.completion_wall_elapsed_ns is not None:
            return False
        timestamp, _local = self._stamp()
        try:
            with self._transaction(diverged=True):
                open_segment = self.segments.open_for_session(context.session_id)
                if open_segment is not None:
                    if (
                        open_segment.segment_type != "focus"
                        or open_segment.focus_phase != "planned"
                    ):
                        raise SessionIntegrityError(
                            "planned completion found the wrong open segment"
                        )
                    self._close_open(context, snapshot, timestamp, "planned_completed")
                self._sync_session(context.session_id, snapshot, "completed", timestamp)
                self._sync_runtime(context.session_id, snapshot, timestamp, force=True)
                self._inject("completion_before_commit")
        except SessionPersistenceError:
            raise
        context.completion_wall_elapsed_ns = snapshot.wall_elapsed_ns
        return True

    def start_overtime(self, snapshot: TimerSnapshot) -> None:
        context = self._require_context()
        if context.completion_wall_elapsed_ns is None:
            raise SessionIntegrityError("overtime requires a persisted planned completion")
        gap_ns = snapshot.wall_elapsed_ns - context.completion_wall_elapsed_ns
        next_group = context.continuity_group_id
        if gap_ns > snapshot.pause_grace_seconds * 1_000_000_000:
            next_group = self._uuid()
        timestamp, local = self._stamp()
        try:
            with self._transaction():
                if self.segments.open_for_session(context.session_id) is not None:
                    raise SessionIntegrityError("overtime cannot start with an open segment")
                self._open_next(
                    context,
                    "focus",
                    "overtime",
                    timestamp,
                    local,
                    snapshot,
                    group_id=next_group,
                )
                self._sync_session(context.session_id, snapshot, "running", timestamp)
                self._sync_runtime(context.session_id, snapshot, timestamp, force=True)
                self._inject("overtime_before_commit")
        except SessionPersistenceError:
            raise
        context.continuity_group_id = next_group

    def record_distraction(self, marker: DistractionMarker, snapshot: TimerSnapshot) -> bool:
        context = self._require_context()
        open_segment = self._require_open(context.session_id, "focus")
        timestamp, local = self._stamp()
        distraction_id = str(
            uuid5(UUID(context.session_id), f"distraction:{marker.marker_sequence}")
        )
        try:
            with self._transaction():
                inserted = self.distractions.insert_if_missing(
                    {
                        "distraction_id": distraction_id,
                        "schema_version": DATA_SCHEMA_VERSION,
                        "session_id": context.session_id,
                        "segment_id": open_segment.segment_id,
                        "device_id": context.device_id,
                        "marked_at_utc": format_utc(timestamp),
                        "marked_at_local": format_local(local),
                        "local_date": local.date().isoformat(),
                        "timezone_name": context.timezone_name,
                        "category_id": marker.category_id,
                        "category_name_snapshot": marker.category_name_snapshot,
                        "elapsed_focus_seconds": snapshot.total_focus_seconds,
                        "remaining_planned_seconds": snapshot.remaining_planned_seconds,
                        "is_overtime": int(marker.is_overtime),
                        "optional_note": None,
                        "created_at_utc": format_utc(timestamp),
                    }
                )
                count = self.distractions.count(context.session_id)
                self.sessions.update(
                    context.session_id,
                    {"distraction_count": count, "updated_at_utc": format_utc(timestamp)},
                )
                self._inject("distraction_before_commit")
        except SessionPersistenceError:
            raise
        return inserted

    def heartbeat(self, snapshot: TimerSnapshot) -> bool:
        context = self._require_context()
        timestamp, _local = self._stamp()
        try:
            with self._transaction():
                changed = self._sync_runtime(context.session_id, snapshot, timestamp, force=False)
                self._inject("heartbeat_before_commit")
        except SessionPersistenceError:
            raise
        return changed

    def finalize(self, snapshot: TimerSnapshot, completion_reason: str) -> SessionSummary:
        context = self._require_context()
        if completion_reason not in {
            "timer_completed",
            "manual_stop",
            "app_close",
            "sleep_detected",
        }:
            raise ValueError("unsupported Phase 6 completion reason")
        timestamp, local = self._stamp()
        status = (
            "recovered" if completion_reason == "sleep_detected" else self._final_status(snapshot)
        )
        try:
            with self._transaction(diverged=True):
                if self.segments.open_for_session(context.session_id) is not None:
                    self._close_open(context, snapshot, timestamp, completion_reason)
                values = self._aggregate_values(snapshot)
                values.update(
                    {
                        "ended_at_utc": format_utc(timestamp),
                        "ended_at_local": format_local(local),
                        "status": status,
                        "completion_reason": completion_reason,
                        "stopped_early_seconds": max(
                            0,
                            snapshot.planned_duration_seconds - snapshot.planned_focus_seconds,
                        ),
                        "completed_planned_timer": int(snapshot.planned_complete),
                        "updated_at_utc": format_utc(timestamp),
                    }
                )
                self.sessions.update(context.session_id, values)
                session = self.sessions.get(context.session_id)
                if session is None:
                    raise SessionIntegrityError("finalized session disappeared")
                checksum = session_checksum(session)
                self.sessions.update(context.session_id, {"record_checksum": checksum})
                self.runtime.delete(context.session_id)
                self._inject("finalize_before_commit")
        except SessionPersistenceError:
            raise
        summary = self.aggregates.summary(context.session_id)
        self._context = None
        if self._post_finalize_sync is not None:
            try:
                synced, message = self._post_finalize_sync(context.session_id)
            except (OSError, RuntimeError, ValueError, sqlite3.Error):
                synced, message = False, "Saved locally; portable sync pending"
            summary = replace(summary, portable_synced=synced, sync_message=message)
        return summary

    @contextmanager
    def _transaction(self, *, diverged: bool = False) -> Iterator[None]:
        if self._blocked_reason:
            raise SessionPersistenceBlockedError(self._blocked_reason)
        if self._busy:
            raise SessionWriteConflictError("another session write is already in progress")
        self._busy = True
        try:
            with self._uow:
                yield
        except SessionPersistenceError:
            if diverged:
                self._blocked_reason = (
                    "Timer and local database state may differ; session actions are blocked."
                )
            raise
        except (sqlite3.Error, LookupError, RuntimeError) as exc:
            if diverged:
                self._blocked_reason = (
                    "Timer and local database state may differ; session actions are blocked."
                )
            raise SessionPersistenceError(f"local session transaction failed: {exc}") from exc
        finally:
            self._busy = False

    def _mark_diverged(self, exc: BaseException) -> None:
        self._blocked_reason = (
            "Timer and local database state may differ; session actions are blocked."
        )
        raise SessionPersistenceBlockedError(f"{self._blocked_reason} {exc}") from exc

    def _require_context(self) -> PersistenceContext:
        if self._context is None:
            raise NoActiveFocusSessionError("there is no active persisted session")
        if self._blocked_reason:
            raise SessionPersistenceBlockedError(self._blocked_reason)
        return self._context

    def _require_open(self, session_id: str, segment_type: str) -> PersistedSegment:
        segment = self.segments.open_for_session(session_id)
        if segment is None or segment.segment_type != segment_type:
            raise SessionIntegrityError(f"expected one open {segment_type} segment")
        return segment

    def _stamp(self) -> tuple[datetime, datetime]:
        utc = require_utc(self._clock.now_utc())
        return utc, utc.astimezone(get_timezone(self._timezone_name))

    @staticmethod
    def _offset_minutes(local: datetime) -> int:
        offset = local.utcoffset()
        if offset is None:
            raise SessionPersistenceError("local timezone has no UTC offset")
        return int(offset.total_seconds() // 60)

    def _insert_segment(
        self,
        segment_id: str,
        session_id: str,
        sequence: int,
        segment_type: str,
        phase: str,
        group_id: str,
        timestamp: datetime,
        local: datetime,
        grace_seconds: int,
    ) -> None:
        utc_text = format_utc(timestamp)
        self.segments.insert(
            {
                "segment_id": segment_id,
                "schema_version": DATA_SCHEMA_VERSION,
                "session_id": session_id,
                "device_id": self._device_id,
                "segment_sequence": sequence,
                "segment_type": segment_type,
                "started_at_utc": utc_text,
                "timezone_name": self._timezone_name,
                "utc_offset_started_minutes": self._offset_minutes(local),
                "counts_as_focus": int(segment_type == "focus"),
                "pause_classification": "none",
                "breaks_continuity": 0,
                "continuity_group_id": group_id,
                "pause_grace_threshold_seconds": grace_seconds,
                "focus_phase": phase,
                "created_at_utc": utc_text,
                "updated_at_utc": utc_text,
            }
        )

    def _open_next(
        self,
        context: PersistenceContext,
        segment_type: str,
        phase: str,
        timestamp: datetime,
        local: datetime,
        snapshot: TimerSnapshot,
        *,
        group_id: str | None = None,
    ) -> None:
        self._insert_segment(
            self._uuid(),
            context.session_id,
            self.segments.next_sequence(context.session_id),
            segment_type,
            phase,
            group_id or context.continuity_group_id,
            timestamp,
            local,
            snapshot.pause_grace_seconds,
        )

    def _close_open(
        self,
        context: PersistenceContext,
        snapshot: TimerSnapshot,
        timestamp: datetime,
        reason: str,
    ) -> None:
        segment = self.segments.open_for_session(context.session_id)
        if segment is None:
            raise SessionIntegrityError("session has no open segment")
        duration = self._segment_duration(
            context.session_id, segment.segment_type, segment.focus_phase, snapshot
        )
        values: dict[str, object] = {
            "ended_at_utc": format_utc(timestamp),
            "duration_seconds": duration,
            "end_reason": reason,
            "updated_at_utc": format_utc(timestamp),
        }
        if segment.segment_type == "pause":
            if context.pause_started_total_ns is None:
                raise SessionIntegrityError("pause monotonic boundary is missing")
            pause_ns = snapshot.total_pause_ns - context.pause_started_total_ns
            if segment.pause_classification == "system_sleep":
                values.update({"pause_classification": "system_sleep", "breaks_continuity": 1})
            else:
                short = pause_ns <= snapshot.pause_grace_seconds * 1_000_000_000
                values.update(
                    {
                        "pause_classification": (
                            "short_grace_pause" if short else "continuity_break"
                        ),
                        "breaks_continuity": int(not short),
                    }
                )
        self.segments.close(
            segment.segment_id,
            values,
        )

    def _segment_duration(
        self,
        session_id: str,
        segment_type: str,
        phase: str,
        snapshot: TimerSnapshot,
    ) -> int:
        if segment_type == "pause":
            target = snapshot.total_pause_seconds
        elif phase == "overtime":
            target = snapshot.overtime_seconds
        else:
            target = snapshot.planned_focus_seconds
        prior = self.segments.finalized_seconds(session_id, segment_type, phase)
        duration = target - prior
        if duration < 0:
            raise SessionIntegrityError("segment duration reconciliation became negative")
        return duration

    def _sync_session(
        self, session_id: str, snapshot: TimerSnapshot, status: str, timestamp: datetime
    ) -> None:
        values = self._aggregate_values(snapshot)
        values.update({"status": status, "updated_at_utc": format_utc(timestamp)})
        self.sessions.update(session_id, values)

    @staticmethod
    def _aggregate_values(snapshot: TimerSnapshot) -> dict[str, object]:
        return {
            "actual_focus_seconds": snapshot.total_focus_seconds,
            "planned_focus_completed_seconds": snapshot.planned_focus_seconds,
            "overtime_seconds": snapshot.overtime_seconds,
            "total_pause_seconds": snapshot.total_pause_seconds,
            "wall_clock_seconds": snapshot.wall_elapsed_seconds,
            "continuous_block_count": snapshot.continuous_block_count,
            "longest_continuous_seconds": snapshot.longest_continuous_seconds,
            "average_continuous_seconds": snapshot.average_continuous_seconds,
            "median_continuous_seconds": snapshot.median_continuous_seconds,
            "pause_count": snapshot.pause_count,
            "short_pause_count": snapshot.short_pause_count,
            "long_pause_count": snapshot.long_pause_count,
        }

    def _sync_runtime(
        self,
        session_id: str,
        snapshot: TimerSnapshot,
        timestamp: datetime,
        *,
        force: bool,
        sleep_started_at_utc: str | None = None,
    ) -> bool:
        values: dict[str, object] = {
            "timer_state": snapshot.state.value,
            "temporary_intention_text": None,
            "remaining_planned_seconds": snapshot.remaining_planned_seconds,
            "is_overtime": int(snapshot.state is TimerState.OVERTIME),
            "last_heartbeat_at_utc": format_utc(timestamp),
            "updated_at_utc": format_utc(timestamp),
            "timer_version": snapshot.version,
            "confirmed_planned_focus_seconds": snapshot.planned_focus_seconds,
            "confirmed_overtime_seconds": snapshot.overtime_seconds,
            "confirmed_pause_seconds": snapshot.total_pause_seconds,
            "confirmed_wall_clock_seconds": snapshot.wall_elapsed_seconds,
            "sleep_started_at_utc": sleep_started_at_utc,
        }
        if force:
            assignments = ", ".join(f"{column} = ?" for column in values)
            cursor = self._connection.execute(
                f"UPDATE runtime_session_state SET {assignments} WHERE session_id = ?",
                (*values.values(), session_id),
            )
            if cursor.rowcount != 1:
                raise SessionIntegrityError("runtime state is missing")
            return True
        return self.runtime.update_if_new_version(session_id, values, snapshot.version)

    @staticmethod
    def _final_status(snapshot: TimerSnapshot) -> str:
        if snapshot.overtime_ns > 0:
            return "completed_with_overtime"
        if snapshot.planned_complete:
            return "completed"
        return "stopped_early"
