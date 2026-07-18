"""Read-only analysis of unfinished runtime and segment state."""

import sqlite3
from collections.abc import Callable

from app.core.ids import new_uuid4
from app.core.time_utils import format_utc, parse_utc
from app.core.wall_clock import SystemWallClock, WallClock, require_utc
from app.database.repositories.recovery_event_repository import RecoveryEventRepository
from app.database.repositories.runtime_state_repository import RuntimeStateRepository
from app.database.repositories.segment_repository import SegmentRepository
from app.database.repositories.session_repository import SessionRepository
from app.recovery.errors import RecoveryIntegrityError
from app.recovery.models import RecoveryAction, RecoveryAnalysis, RecoveryType


class RecoveryAnalyzer:
    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        wall_clock: WallClock | None = None,
        uuid_provider: Callable[[], str] = new_uuid4,
    ) -> None:
        self._runtime = RuntimeStateRepository(connection)
        self._sessions = SessionRepository(connection)
        self._segments = SegmentRepository(connection)
        self._events = RecoveryEventRepository(connection)
        self._clock = wall_clock or SystemWallClock()
        self._uuid = uuid_provider

    def analyze_all(self) -> tuple[RecoveryAnalysis, ...]:
        return tuple(self.analyze(item.session_id) for item in self._runtime.all())

    def analyze(self, session_id: str) -> RecoveryAnalysis:
        runtime = self._runtime.get(session_id)
        session = self._sessions.get(session_id)
        if runtime is None or session is None:
            raise RecoveryIntegrityError("session or runtime state is missing")
        detected = require_utc(self._clock.now_utc())
        boundary_text = runtime.last_heartbeat_at_utc or runtime.updated_at_utc
        boundary = parse_utc(boundary_text)
        unknown = max(0, int((detected - boundary).total_seconds()))
        open_segment = self._segments.open_for_session(session_id)
        warnings: list[str] = []
        if open_segment is None and runtime.timer_state not in {"completed", "stopped"}:
            warnings.append("runtime state has no open segment")
        if runtime.confirmed_planned_focus_seconds > session.planned_focus_seconds:
            warnings.append("confirmed planned focus exceeds the session plan")
        recovery_type = self._type(runtime.timer_state, runtime.sleep_started_at_utc is not None)
        can_resume = bool(
            recovery_type is RecoveryType.SYSTEM_SLEEP
            and runtime.timer_state == "paused"
            and open_segment is not None
            and open_segment.segment_type == "pause"
            and open_segment.pause_classification == "system_sleep"
        )
        recommended = (
            RecoveryAction.RESUME_AFTER_SLEEP if can_resume else RecoveryAction.SAVE_CONFIRMED
        )
        prior = self._events.latest_for_session(session_id)
        event_id = (
            prior.recovery_event_id
            if prior is not None and prior.selected_action is None
            else self._uuid()
        )
        return RecoveryAnalysis(
            event_id,
            session.session_id,
            session.category_name_snapshot,
            session.planned_focus_seconds,
            runtime.confirmed_planned_focus_seconds,
            runtime.confirmed_overtime_seconds,
            runtime.confirmed_pause_seconds,
            runtime.confirmed_wall_clock_seconds,
            runtime.last_heartbeat_at_utc,
            boundary_text,
            format_utc(detected),
            unknown,
            runtime.timer_state,
            None if open_segment is None else open_segment.segment_id,
            None if open_segment is None else open_segment.segment_type,
            recovery_type,
            can_resume,
            recommended,
            tuple(warnings),
        )

    @staticmethod
    def _type(timer_state: str, slept: bool) -> RecoveryType:
        if slept:
            return RecoveryType.SYSTEM_SLEEP
        if timer_state == "overtime":
            return RecoveryType.OVERTIME_INTERRUPTED
        if timer_state == "paused":
            return RecoveryType.PAUSED_INTERRUPTED
        if timer_state == "completed":
            return RecoveryType.COMPLETED_NOT_FINALIZED
        return RecoveryType.CRASH
