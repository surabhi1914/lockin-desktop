from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.bootstrap import run_phase0_bootstrap
from app.core.ids import new_uuid4
from app.core.paths import PathConfig
from app.core.wall_clock import ManualWallClock
from app.database.migrations import initialize_database
from app.models.category import Category
from app.models.focus_session_draft import FocusSessionDraft
from app.recovery.errors import RecoveryAlreadyResolvedError, RecoveryIntegrityError
from app.recovery.models import RecoveryAction, RecoveryType
from app.recovery.recovery_service import RecoveryService
from app.services.portable_sync_service import PortableSyncService
from app.services.session_integrity_service import verify_session_integrity
from app.services.session_persistence_service import SessionPersistenceService
from app.timer import ManualClock, TimerConfig, TimerEngine


class RecoveryHarness:
    def __init__(self, tmp_path: Path, *, injector=None) -> None:
        self.connection = initialize_database(tmp_path / "lockin.sqlite3")
        self.device_id = new_uuid4()
        self.category_id = new_uuid4()
        self.wall = ManualWallClock(datetime(2026, 7, 17, 16, 0, tzinfo=UTC))
        stamp = "2026-07-17T16:00:00Z"
        self.connection.execute(
            "INSERT INTO devices VALUES (?, 'Recovery test', ?, ?)",
            (self.device_id, stamp, stamp),
        )
        self.connection.execute(
            "INSERT INTO categories VALUES (?, 'Recovery', NULL, 1, ?, ?)",
            (self.category_id, stamp, stamp),
        )
        self.connection.commit()
        self.category = Category(self.category_id, "Recovery", None, True, stamp, stamp)
        self.draft = FocusSessionDraft(
            60, self.category_id, "Recovery", "never persisted", False, True, False, True, False, 10
        )
        self.clock = ManualClock()
        self.engine = TimerEngine(TimerConfig(60, 10, True), self.clock)
        self.persistence = SessionPersistenceService(
            self.connection, self.device_id, wall_clock=self.wall
        )
        self.recovery = RecoveryService(
            self.connection,
            wall_clock=self.wall,
            failure_injector=injector,
            post_recovery_sync=lambda _session_id: (True, "Recovered and synced"),
        )

    def start(self) -> str:
        context = self.persistence.start_session(self.draft, self.category, self.engine.start())
        return context.session_id

    def advance(self, seconds: int) -> None:
        self.clock.advance_seconds(seconds)
        self.wall.advance(seconds=seconds)


def test_crash_save_uses_last_heartbeat_and_excludes_unknown_gap(tmp_path: Path) -> None:
    harness = RecoveryHarness(tmp_path)
    session_id = harness.start()
    harness.advance(12)
    assert harness.persistence.heartbeat(harness.engine.snapshot())
    harness.wall.advance(seconds=38)
    analysis = harness.recovery.analyses()[0]
    assert analysis.recovery_type is RecoveryType.CRASH
    assert analysis.confirmed_focus_seconds == 12
    assert analysis.unknown_gap_seconds == 38
    assert analysis.confirmed_boundary_at_utc == "2026-07-17T16:00:12Z"
    result = harness.recovery.save_confirmed(session_id)
    assert result.action is RecoveryAction.SAVE_CONFIRMED
    assert result.confirmed_focus_seconds == 12 and result.unknown_gap_seconds == 38
    session = harness.persistence.sessions.get(session_id)
    assert session is not None
    assert session.status == "recovered" and session.actual_focus_seconds == 12
    assert session.ended_at_utc == "2026-07-17T16:00:12Z"
    assert harness.persistence.runtime.get(session_id) is None
    audit = harness.connection.execute(
        "SELECT * FROM recovery_events WHERE session_id=?", (session_id,)
    ).fetchone()
    assert audit["selected_action"] == "save_confirmed"
    assert audit["unknown_gap_seconds"] == 38
    assert "intention" not in set(audit.keys())
    assert verify_session_integrity(harness.connection).healthy
    with pytest.raises(RecoveryAlreadyResolvedError):
        harness.recovery.save_confirmed(session_id)


def test_discard_preserves_audit_and_unblocks_runtime(tmp_path: Path) -> None:
    harness = RecoveryHarness(tmp_path)
    session_id = harness.start()
    harness.advance(4)
    harness.persistence.heartbeat(harness.engine.snapshot())
    result = harness.recovery.discard(session_id)
    assert result.final_status == "discarded"
    session = harness.persistence.sessions.get(session_id)
    assert session is not None and session.status == "discarded"
    assert harness.persistence.runtime.get(session_id) is None
    assert (
        harness.connection.execute(
            "SELECT COUNT(*) FROM recovery_events WHERE session_id=?", (session_id,)
        ).fetchone()[0]
        == 1
    )


def test_system_sleep_pause_is_nonfocus_and_forces_new_continuity_group(
    tmp_path: Path,
) -> None:
    harness = RecoveryHarness(tmp_path)
    session_id = harness.start()
    harness.advance(5)
    paused = harness.engine.pause()
    harness.persistence.system_sleep_pause(paused)
    harness.recovery.record_sleep_pause(session_id)
    runtime = harness.persistence.runtime.get(session_id)
    assert runtime is not None and runtime.sleep_started_at_utc == "2026-07-17T16:00:05Z"
    open_pause = harness.persistence.segments.open_for_session(session_id)
    assert open_pause is not None
    assert open_pause.pause_classification == "system_sleep" and open_pause.breaks_continuity
    first_group = harness.persistence.segments.list_for_session(session_id)[0].continuity_group_id
    harness.advance(120)
    resumed = harness.engine.resume()
    harness.persistence.resume(resumed)
    harness.recovery.record_sleep_resume(session_id)
    segments = harness.persistence.segments.list_for_session(session_id)
    assert segments[1].duration_seconds == 120
    assert segments[1].pause_classification == "system_sleep"
    assert segments[2].continuity_group_id != first_group
    assert harness.engine.snapshot().total_focus_seconds == 5
    assert harness.engine.snapshot().total_pause_seconds == 120


def test_recovery_transaction_rolls_back_on_injected_failure(tmp_path: Path) -> None:
    def fail(point: str) -> None:
        if point == "before_recovery_commit":
            raise RuntimeError("injected")

    harness = RecoveryHarness(tmp_path, injector=fail)
    session_id = harness.start()
    harness.advance(3)
    harness.persistence.heartbeat(harness.engine.snapshot())
    with pytest.raises(RecoveryIntegrityError, match="injected"):
        harness.recovery.save_confirmed(session_id)
    assert harness.persistence.runtime.get(session_id) is not None
    session = harness.persistence.sessions.get(session_id)
    assert session is not None and session.ended_at_utc is None


def test_overtime_recovery_preserves_planned_overtime_split(tmp_path: Path) -> None:
    harness = RecoveryHarness(tmp_path)
    harness.draft = FocusSessionDraft(
        5,
        harness.category_id,
        "Recovery",
        None,
        False,
        True,
        False,
        True,
        False,
        10,
    )
    harness.engine = TimerEngine(TimerConfig(5, 10, True), harness.clock)
    session_id = harness.start()
    harness.advance(5)
    completed = harness.engine.snapshot()
    harness.persistence.planned_completed(completed)
    harness.persistence.start_overtime(completed)
    harness.engine.start_overtime()
    harness.advance(7)
    harness.persistence.heartbeat(harness.engine.snapshot())
    analysis = harness.recovery.analyzer.analyze(session_id)
    assert analysis.recovery_type is RecoveryType.OVERTIME_INTERRUPTED
    assert analysis.confirmed_planned_focus_seconds == 5
    assert analysis.confirmed_overtime_seconds == 7
    result = harness.recovery.save_confirmed(session_id)
    assert result.confirmed_focus_seconds == 12
    session = harness.persistence.sessions.get(session_id)
    assert session is not None
    assert session.planned_focus_completed_seconds == 5 and session.overtime_seconds == 7


def test_crash_while_manually_paused_preserves_confirmed_pause_only(tmp_path: Path) -> None:
    harness = RecoveryHarness(tmp_path)
    session_id = harness.start()
    harness.advance(6)
    harness.persistence.pause(harness.engine.pause())
    harness.advance(4)
    harness.persistence.heartbeat(harness.engine.snapshot())
    harness.wall.advance(seconds=30)
    analysis = harness.recovery.analyzer.analyze(session_id)
    assert analysis.recovery_type is RecoveryType.PAUSED_INTERRUPTED
    assert analysis.confirmed_focus_seconds == 6
    assert analysis.confirmed_pause_seconds == 4
    assert analysis.unknown_gap_seconds == 30
    harness.recovery.save_confirmed(session_id)
    session = harness.persistence.sessions.get(session_id)
    assert session is not None
    assert session.actual_focus_seconds == 6 and session.total_pause_seconds == 4


def test_recovered_session_is_exported_and_repeat_sync_is_idempotent(tmp_path: Path) -> None:
    harness = RecoveryHarness(tmp_path)
    assert run_phase0_bootstrap(
        config=PathConfig(tmp_path, tmp_path, tmp_path / "portable")
    ).success
    session_id = harness.start()
    harness.advance(8)
    harness.persistence.heartbeat(harness.engine.snapshot())
    sync = PortableSyncService(
        harness.connection,
        tmp_path / "portable",
        tmp_path / "portable-backups",
    )
    harness.recovery = RecoveryService(
        harness.connection,
        wall_clock=harness.wall,
        post_recovery_sync=lambda target: (
            (result := sync.sync_session(target)).success,
            result.message,
        ),
    )
    result = harness.recovery.save_confirmed(session_id)
    assert result.portable_synced
    assert next((tmp_path / "portable" / "sessions").rglob("*.csv")).is_file()
    repeated = sync.sync_session(session_id)
    assert repeated.success and repeated.counts.sessions == 0
    assert repeated.counts.skipped >= 3
