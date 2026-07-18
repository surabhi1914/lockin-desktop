from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.ids import new_uuid4
from app.core.wall_clock import ManualWallClock
from app.database.migrations import initialize_database
from app.database.repositories.runtime_state_repository import RuntimeStateRepository
from app.database.repositories.session_repository import SessionRepository
from app.models.category import Category
from app.models.errors import SessionPersistenceError
from app.models.focus_session_draft import FocusSessionDraft
from app.services.distraction_marker_service import DistractionMarkerService
from app.services.session_integrity_service import verify_session_integrity
from app.services.session_persistence_service import SessionPersistenceService
from app.services.unfinished_detector_service import UnfinishedDetectorService
from app.timer import ManualClock, TimerConfig, TimerEngine


class Harness:
    def __init__(self, tmp_path: Path, *, injector=None) -> None:
        self.connection = initialize_database(tmp_path / "lockin.sqlite3")
        self.device_id = new_uuid4()
        self.category_id = new_uuid4()
        self.wall = ManualWallClock(datetime(2026, 7, 16, 16, 0, tzinfo=UTC))
        timestamp = "2026-07-16T16:00:00Z"
        self.connection.execute(
            "INSERT INTO devices VALUES (?, 'Test device', ?, ?)",
            (self.device_id, timestamp, timestamp),
        )
        self.connection.execute(
            "INSERT INTO categories VALUES (?, 'Research', NULL, 1, ?, ?)",
            (self.category_id, timestamp, timestamp),
        )
        self.connection.commit()
        self.category = Category(self.category_id, "Research", None, True, timestamp, timestamp)
        self.draft = FocusSessionDraft(
            20,
            self.category_id,
            "Research",
            "Never persist this intention",
            False,
            True,
            False,
            True,
            False,
            10,
        )
        self.clock = ManualClock()
        self.engine = TimerEngine(TimerConfig(20, 10, True), self.clock)
        self.service = SessionPersistenceService(
            self.connection,
            self.device_id,
            wall_clock=self.wall,
            failure_injector=injector,
        )

    def start(self):
        snapshot = self.engine.start()
        return self.service.start_session(self.draft, self.category, snapshot)

    def advance(self, seconds: int):
        self.clock.advance_seconds(seconds)
        self.wall.advance(seconds=seconds)
        return self.engine.snapshot()


def test_complete_session_is_finalized_with_checksum_and_no_intention(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    context = harness.start()
    runtime = harness.connection.execute(
        "SELECT * FROM runtime_session_state WHERE session_id = ?", (context.session_id,)
    ).fetchone()
    assert runtime["temporary_intention_text"] is None
    snapshot = harness.advance(20)
    assert harness.service.planned_completed(snapshot)
    stopped = harness.engine.stop()
    summary = harness.service.finalize(stopped, "timer_completed")
    assert summary.status == "completed"
    assert summary.saved_locally
    session = harness.service.sessions.get(context.session_id)
    assert session is not None
    assert session.actual_focus_seconds == 20
    assert session.planned_focus_completed_seconds == 20
    assert session.record_checksum is not None
    assert harness.service.runtime.get(context.session_id) is None
    assert verify_session_integrity(harness.connection).healthy


def test_early_stop_and_remainder_allocation_reconcile_segments(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    context = harness.start()
    harness.clock.advance_ns(1_500_000_000)
    harness.wall.advance(seconds=2)
    paused = harness.engine.pause()
    harness.service.pause(paused)
    harness.clock.advance_ns(1_500_000_000)
    harness.wall.advance(seconds=2)
    resumed = harness.engine.resume()
    harness.service.resume(resumed)
    harness.clock.advance_ns(1_500_000_000)
    harness.wall.advance(seconds=2)
    stopped = harness.engine.stop()
    summary = harness.service.finalize(stopped, "manual_stop")
    assert summary.status == "stopped_early"
    assert summary.total_focus_seconds == 3
    assert summary.total_pause_seconds == 1
    segments = harness.service.segments.list_for_session(context.session_id)
    assert sum(item.duration_seconds for item in segments if item.counts_as_focus) == 3
    assert sum(item.duration_seconds for item in segments if not item.counts_as_focus) == 1
    assert segments[1].pause_classification == "short_grace_pause"
    assert verify_session_integrity(harness.connection).healthy


def test_long_pause_breaks_continuity_and_starts_new_group(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    context = harness.start()
    harness.advance(2)
    harness.service.pause(harness.engine.pause())
    harness.advance(11)
    harness.service.resume(harness.engine.resume())
    harness.advance(2)
    stopped = harness.engine.stop()
    harness.service.finalize(stopped, "manual_stop")
    segments = harness.service.segments.list_for_session(context.session_id)
    assert segments[1].pause_classification == "continuity_break"
    assert segments[1].breaks_continuity
    assert segments[0].continuity_group_id != segments[2].continuity_group_id


def test_explicit_overtime_is_separate_and_distractions_are_durable(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    context = harness.start()
    completed = harness.advance(20)
    harness.service.planned_completed(completed)
    harness.advance(4)
    harness.service.start_overtime(harness.engine.snapshot())
    harness.engine.start_overtime()
    harness.advance(7)
    markers = DistractionMarkerService()
    for _ in range(3):
        snapshot = harness.engine.snapshot()
        markers.mark(
            snapshot,
            harness.category,
            before_append=lambda marker, current=snapshot: harness.service.record_distraction(
                marker, current
            ),
        )
    stopped = harness.engine.stop()
    summary = harness.service.finalize(stopped, "manual_stop")
    assert summary.status == "completed_with_overtime"
    assert summary.planned_focus_seconds == 20
    assert summary.overtime_seconds == 7
    assert summary.total_focus_seconds == 27
    assert summary.distraction_count == 3
    assert len(harness.service.distractions.list_for_session(context.session_id)) == 3
    assert verify_session_integrity(harness.connection).healthy


def test_heartbeat_skips_same_version_and_unfinished_detection_is_read_only(
    tmp_path: Path,
) -> None:
    harness = Harness(tmp_path)
    context = harness.start()
    snapshot = harness.engine.snapshot()
    before = harness.service.runtime.get(context.session_id)
    assert before is not None
    assert not harness.service.heartbeat(snapshot)
    harness.advance(5)
    changed = harness.engine.snapshot()
    assert harness.service.heartbeat(changed)
    detected = UnfinishedDetectorService(
        RuntimeStateRepository(harness.connection), SessionRepository(harness.connection)
    ).detect()
    assert len(detected) == 1
    assert detected[0].session_id == context.session_id
    assert harness.connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_failure_injection_rolls_back_whole_pause_and_blocks_future_actions(
    tmp_path: Path,
) -> None:
    def fail(point: str) -> None:
        if point == "pause_before_commit":
            raise RuntimeError("injected failure")

    harness = Harness(tmp_path, injector=fail)
    context = harness.start()
    harness.advance(3)
    paused = harness.engine.pause()
    with pytest.raises(SessionPersistenceError, match="injected failure"):
        harness.service.pause(paused)
    session = harness.service.sessions.get(context.session_id)
    assert session is not None and session.status == "running"
    segment = harness.service.segments.open_for_session(context.session_id)
    assert segment is not None and segment.segment_type == "focus"
    assert harness.service.blocked_reason is not None


def test_start_failure_leaves_no_partial_rows(tmp_path: Path) -> None:
    def fail(point: str) -> None:
        if point == "start_before_commit":
            raise RuntimeError("injected start failure")

    harness = Harness(tmp_path, injector=fail)
    with pytest.raises(SessionPersistenceError):
        harness.start()
    assert harness.connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    assert harness.connection.execute("SELECT COUNT(*) FROM segments").fetchone()[0] == 0
    assert (
        harness.connection.execute("SELECT COUNT(*) FROM runtime_session_state").fetchone()[0] == 0
    )


def test_database_enforces_one_open_segment_per_session(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    context = harness.start()
    row = harness.connection.execute(
        "SELECT * FROM segments WHERE session_id = ?", (context.session_id,)
    ).fetchone()
    values = dict(row)
    values["segment_id"] = new_uuid4()
    values["segment_sequence"] = 2
    columns = tuple(values)
    with pytest.raises(Exception, match="UNIQUE"):
        harness.connection.execute(
            f"INSERT INTO segments ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})",
            tuple(values[column] for column in columns),
        )


def test_stop_while_paused_finalizes_pause_classification(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    context = harness.start()
    harness.advance(2)
    harness.service.pause(harness.engine.pause())
    harness.advance(12)
    stopped = harness.engine.stop()
    harness.service.finalize(stopped, "manual_stop")
    pause = harness.service.segments.list_for_session(context.session_id)[1]
    assert pause.pause_classification == "continuity_break"
    assert pause.duration_seconds == 12


def test_duplicate_completion_and_distraction_are_idempotent(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    harness.start()
    completed = harness.advance(20)
    assert harness.service.planned_completed(completed)
    assert not harness.service.planned_completed(completed)
    harness.service.start_overtime(harness.engine.snapshot())
    harness.engine.start_overtime()
    marker_service = DistractionMarkerService()
    snapshot = harness.engine.snapshot()
    marker = marker_service.mark(snapshot, harness.category)
    assert harness.service.record_distraction(marker, snapshot)
    assert not harness.service.record_distraction(marker, snapshot)
    assert harness.connection.execute("SELECT COUNT(*) FROM distractions").fetchone()[0] == 1


def test_integrity_report_identifies_corrupt_finalized_state(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    context = harness.start()
    completed = harness.advance(20)
    harness.service.planned_completed(completed)
    harness.service.finalize(harness.engine.stop(), "timer_completed")
    harness.connection.execute("PRAGMA foreign_keys = OFF")
    harness.connection.execute(
        """
        UPDATE sessions SET device_id = ?, actual_focus_seconds = 999,
            distraction_count = 9, record_checksum = 'bad'
        WHERE session_id = ?
        """,
        (new_uuid4(), context.session_id),
    )
    harness.connection.execute(
        "UPDATE segments SET segment_sequence = 2, ended_at_utc = NULL WHERE session_id = ?",
        (context.session_id,),
    )
    harness.connection.execute(
        """
        INSERT INTO runtime_session_state (
          session_id, timer_state, temporary_intention_text, remaining_planned_seconds,
          is_overtime, last_heartbeat_at_utc, updated_at_utc, timer_version
        ) VALUES (?, 'stopped', NULL, 0, 0, NULL, '2026-07-16T16:00:20Z', 1)
        """,
        (context.session_id,),
    )
    harness.connection.commit()
    harness.connection.execute("PRAGMA foreign_keys = ON")
    report = verify_session_integrity(harness.connection)
    assert not report.healthy
    combined = " ".join(report.errors)
    assert "foreign-key" in combined
    assert "open segment" in combined
    assert "runtime state" in combined
    assert "non-contiguous" in combined
    assert "distraction aggregate" in combined
    assert "actual focus" in combined
    assert "checksum" in combined
