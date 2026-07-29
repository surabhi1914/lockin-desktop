"""Transactional confirmed-time recovery and immutable audit coordination."""

import sqlite3
from collections.abc import Callable

from app.core.ids import new_uuid4
from app.core.time_utils import format_local, format_utc, get_timezone, parse_utc
from app.core.wall_clock import SystemWallClock, WallClock, require_utc
from app.database.repositories.recovery_event_repository import RecoveryEventRepository
from app.database.repositories.runtime_state_repository import RuntimeStateRepository
from app.database.repositories.segment_repository import SegmentRepository
from app.database.repositories.session_repository import SessionRepository
from app.database.unit_of_work import UnitOfWork
from app.recovery.errors import RecoveryAlreadyResolvedError, RecoveryIntegrityError
from app.recovery.models import RecoveryAction, RecoveryAnalysis, RecoveryResult, RecoveryType
from app.recovery.recovery_analyzer import RecoveryAnalyzer
from app.services.session_checksum_service import session_checksum

PostRecoverySync = Callable[[str], tuple[bool, str]]
FailureInjector = Callable[[str], None]


class RecoveryService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        wall_clock: WallClock | None = None,
        uuid_provider: Callable[[], str] = new_uuid4,
        post_recovery_sync: PostRecoverySync | None = None,
        failure_injector: FailureInjector | None = None,
    ) -> None:
        self._connection = connection
        self._clock = wall_clock or SystemWallClock()
        self._uuid = uuid_provider
        self._sync = post_recovery_sync
        self._inject = failure_injector or (lambda _point: None)
        self._runtime = RuntimeStateRepository(connection)
        self._sessions = SessionRepository(connection)
        self._segments = SegmentRepository(connection)
        self._events = RecoveryEventRepository(connection)
        self._uow = UnitOfWork(connection)
        self.analyzer = RecoveryAnalyzer(
            connection, wall_clock=self._clock, uuid_provider=uuid_provider
        )

    def analyses(self) -> tuple[RecoveryAnalysis, ...]:
        analyses = self.analyzer.analyze_all()
        for analysis in analyses:
            self._ensure_audit(analysis)
        return analyses

    def save_confirmed(self, session_id: str) -> RecoveryResult:
        return self._resolve(session_id, RecoveryAction.SAVE_CONFIRMED)

    def discard(self, session_id: str) -> RecoveryResult:
        return self._resolve(session_id, RecoveryAction.DISCARD)

    def record_sleep_pause(self, session_id: str) -> str:
        analysis = self.analyzer.analyze(session_id)
        now = format_utc(require_utc(self._clock.now_utc()))
        existing = self._events.latest_for_session(session_id)
        event_id = (
            existing.recovery_event_id
            if existing and existing.selected_action is None
            else self._uuid()
        )
        with self._uow:
            if existing is None or existing.selected_action is not None:
                self._events.insert(
                    self._audit_values(
                        analysis,
                        event_id=event_id,
                        event_type=RecoveryType.SYSTEM_SLEEP.value,
                        selected_action=RecoveryAction.AUTO_PAUSE.value,
                        finalized_at_utc=now,
                    )
                )
        return event_id

    def record_sleep_resume(self, session_id: str) -> None:
        event = self._events.latest_for_session(session_id)
        if event is None:
            return
        now = format_utc(require_utc(self._clock.now_utc()))
        with self._uow:
            self._events.update(
                event.recovery_event_id,
                {
                    "selected_action": RecoveryAction.RESUME_AFTER_SLEEP.value,
                    "finalized_at_utc": now,
                    "updated_at_utc": now,
                },
            )

    def _resolve(self, session_id: str, action: RecoveryAction) -> RecoveryResult:
        if self._runtime.get(session_id) is None:
            raise RecoveryAlreadyResolvedError("the recovery state is already resolved")
        analysis = self.analyzer.analyze(session_id)
        self._ensure_audit(analysis)
        status = "discarded" if action is RecoveryAction.DISCARD else "recovered"
        reason = (
            "sleep_detected"
            if analysis.recovery_type is RecoveryType.SYSTEM_SLEEP
            else "crash_recovery"
        )
        boundary = parse_utc(analysis.confirmed_boundary_at_utc)
        session = self._sessions.get(session_id)
        if session is None:
            raise RecoveryIntegrityError("recovery session disappeared")
        local = boundary.astimezone(get_timezone(session.timezone_name))
        finalized_at = format_utc(require_utc(self._clock.now_utc()))
        try:
            with self._uow:
                self._close_confirmed_open_segment(analysis, finalized_at)
                metrics = self._continuous_metrics(session_id)
                values: dict[str, object] = {
                    "ended_at_utc": format_utc(boundary),
                    "ended_at_local": format_local(local),
                    "actual_focus_seconds": analysis.confirmed_focus_seconds,
                    "planned_focus_completed_seconds": analysis.confirmed_planned_focus_seconds,
                    "overtime_seconds": analysis.confirmed_overtime_seconds,
                    "total_pause_seconds": analysis.confirmed_pause_seconds,
                    "wall_clock_seconds": analysis.confirmed_wall_clock_seconds,
                    **metrics,
                    "status": status,
                    "completion_reason": reason,
                    "entry_source": "recovery",
                    "stopped_early_seconds": max(
                        0,
                        session.planned_focus_seconds - analysis.confirmed_planned_focus_seconds,
                    ),
                    "completed_planned_timer": int(
                        analysis.confirmed_planned_focus_seconds == session.planned_focus_seconds
                    ),
                    "updated_at_utc": finalized_at,
                }
                self._sessions.update(session_id, values)
                updated = self._sessions.get(session_id)
                if updated is None:
                    raise RecoveryIntegrityError("recovered session disappeared")
                self._sessions.update(session_id, {"record_checksum": session_checksum(updated)})
                self._runtime.delete(session_id)
                self._events.update(
                    analysis.recovery_event_id,
                    {
                        "selected_action": action.value,
                        "finalized_at_utc": finalized_at,
                        "integrity_result": "confirmed_time_reconciled",
                        "updated_at_utc": finalized_at,
                    },
                )
                self._inject("before_recovery_commit")
        except (sqlite3.Error, LookupError, RuntimeError) as exc:
            raise RecoveryIntegrityError(f"recovery transaction failed: {exc}") from exc
        synced, message = self._sync_result(session_id, status)
        return RecoveryResult(
            session_id,
            action,
            status,
            analysis.confirmed_focus_seconds,
            analysis.unknown_gap_seconds,
            synced,
            message,
        )

    def _close_confirmed_open_segment(
        self, analysis: RecoveryAnalysis, updated_at_utc: str
    ) -> None:
        segment = self._segments.open_for_session(analysis.session_id)
        if segment is None:
            return
        if segment.segment_type == "pause":
            target = analysis.confirmed_pause_seconds
        elif segment.focus_phase == "overtime":
            target = analysis.confirmed_overtime_seconds
        else:
            target = analysis.confirmed_planned_focus_seconds
        prior = self._segments.finalized_seconds(
            analysis.session_id, segment.segment_type, segment.focus_phase
        )
        duration = max(0, target - prior)
        values: dict[str, object] = {
            "ended_at_utc": analysis.confirmed_boundary_at_utc,
            "duration_seconds": duration,
            "end_reason": "recovered_confirmed_boundary",
            "updated_at_utc": updated_at_utc,
        }
        if segment.segment_type == "pause" and segment.pause_classification != "system_sleep":
            values.update({"pause_classification": "continuity_break", "breaks_continuity": 1})
        self._segments.close(segment.segment_id, values)

    def _continuous_metrics(self, session_id: str) -> dict[str, object]:
        segments = self._segments.list_for_session(session_id)
        blocks: list[int] = []
        current_key: str | None = None
        current_total = 0
        for segment in segments:
            if not segment.counts_as_focus:
                continue
            key = segment.continuity_group_id or segment.segment_id
            if current_key is not None and key != current_key:
                blocks.append(current_total)
                current_total = 0
            current_key = key
            current_total += segment.duration_seconds
        if current_key is not None:
            blocks.append(current_total)
        ordered = sorted(blocks)
        count = len(ordered)
        average = sum(ordered) // count if count else 0
        if not count:
            median = 0
        elif count % 2:
            median = ordered[count // 2]
        else:
            median = (ordered[count // 2 - 1] + ordered[count // 2]) // 2
        pauses = [item for item in segments if item.segment_type == "pause"]
        return {
            "continuous_block_count": count,
            "longest_continuous_seconds": max(ordered, default=0),
            "average_continuous_seconds": average,
            "median_continuous_seconds": median,
            "pause_count": len(pauses),
            "short_pause_count": sum(
                item.pause_classification == "short_grace_pause" for item in pauses
            ),
            "long_pause_count": sum(
                item.pause_classification in {"continuity_break", "system_sleep"} for item in pauses
            ),
        }

    def _ensure_audit(self, analysis: RecoveryAnalysis) -> None:
        existing = self._events.latest_for_session(analysis.session_id)
        if existing is not None and existing.recovery_event_id == analysis.recovery_event_id:
            return
        with self._uow:
            self._events.insert(self._audit_values(analysis))

    def _audit_values(
        self,
        analysis: RecoveryAnalysis,
        *,
        event_id: str | None = None,
        event_type: str | None = None,
        selected_action: str | None = None,
        finalized_at_utc: str | None = None,
    ) -> dict[str, object]:
        return {
            "recovery_event_id": event_id or analysis.recovery_event_id,
            "session_id": analysis.session_id,
            "detected_at_utc": analysis.detected_at_utc,
            "event_type": event_type or analysis.recovery_type.value,
            "last_heartbeat_at_utc": analysis.last_heartbeat_at_utc,
            "confirmed_boundary_at_utc": analysis.confirmed_boundary_at_utc,
            "unknown_gap_seconds": analysis.unknown_gap_seconds,
            "selected_action": selected_action,
            "finalized_at_utc": finalized_at_utc,
            "original_timer_state": analysis.original_timer_state,
            "integrity_result": "; ".join(analysis.warnings) or "structure_valid",
            "created_at_utc": analysis.detected_at_utc,
            "updated_at_utc": finalized_at_utc or analysis.detected_at_utc,
        }

    def _sync_result(self, session_id: str, status: str) -> tuple[bool, str]:
        if self._sync is None or status == "discarded":
            return status == "discarded", (
                "Discarded session retained locally"
                if status == "discarded"
                else "Recovered session saved locally"
            )
        try:
            return self._sync(session_id)
        except (OSError, RuntimeError, ValueError, sqlite3.Error):
            return False, "Recovered locally; portable sync pending"
