from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.models.focus_summary import FocusSummaryStatus
from app.timer.enums import TimerState
from app.ui.focus.focus_experience import FocusViewStage
from tests.phase4_helpers import build_phase4_harness, focus_draft


def test_ritual_boundary_completion_wait_overtime_and_summary(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    harness = build_phase4_harness(qapp, tmp_path)
    try:
        draft = focus_draft(harness, duration=10, ritual=True, intention="Finish one section")
        harness.service.start_focus(draft)
        assert harness.service.stage is FocusViewStage.RITUAL
        assert harness.coordinator.has_active_session
        assert not harness.coordinator.has_active_preview
        harness.clock.advance_seconds(50)
        assert not harness.coordinator.has_active_preview
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: harness.service.stage is FocusViewStage.FOCUS,
            timeout=1000,
        )
        assert harness.coordinator.engine.state is TimerState.RUNNING
        assert harness.coordinator.engine.snapshot().total_focus_seconds == 0

        harness.clock.advance_seconds(10)
        harness.coordinator.adapter.poll_once()
        assert harness.service.stage is FocusViewStage.COMPLETION
        assert harness.experience.completion_presented
        assert not harness.experience.show_completion(
            harness.coordinator.engine.snapshot(), overtime_enabled=True
        )
        completed = harness.coordinator.engine.snapshot()
        harness.clock.advance_seconds(20)
        harness.coordinator.adapter.poll_once()
        assert harness.coordinator.engine.snapshot().total_focus_ns == completed.total_focus_ns

        harness.experience.overtime_requested.emit()
        assert harness.coordinator.engine.state is TimerState.OVERTIME
        harness.clock.advance_seconds(4)
        harness.coordinator.adapter.poll_once()
        harness.experience.pause_requested.emit()
        harness.clock.advance_seconds(2)
        harness.coordinator.adapter.poll_once()
        harness.experience.resume_requested.emit()
        harness.clock.advance_seconds(3)
        harness.coordinator.adapter.poll_once()
        assert harness.service.request_stop()
        summary = harness.service.current_summary
        assert summary is not None
        assert summary.status is FocusSummaryStatus.COMPLETED_WITH_OVERTIME
        assert summary.planned_focus_seconds == 10
        assert summary.overtime_seconds == 7
        assert summary.total_pause_seconds == 2
        assert harness.service.stage is FocusViewStage.SUMMARY
        harness.service.return_to_setup()
        assert not harness.service.has_active_session
        assert harness.setup.intention_input.text() == ""
        assert not harness.window.focus_view_active
    finally:
        harness.close()


def test_monitor_removal_recovers_window_without_resetting_engine(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    harness = build_phase4_harness(qapp, tmp_path)
    try:
        harness.window.show()
        harness.service.start_focus(focus_draft(harness, full_screen=False))
        engine = harness.coordinator.engine
        harness.clock.advance_seconds(3)
        harness.coordinator.adapter.poll_once()
        before = engine.snapshot().total_focus_ns
        assert harness.window_service.enter_full_screen()
        harness.experience.set_full_screen(True)
        target = harness.window_service.target_screen
        assert target is not None
        stack_count = harness.window.root_stack.count()
        harness.window_service.handle_screen_removed(target)
        assert not harness.window_service.is_full_screen
        assert harness.coordinator.engine is engine
        assert engine.snapshot().total_focus_ns == before
        assert harness.window.root_stack.count() == stack_count == 2
    finally:
        harness.close()


def test_minimize_and_hide_do_not_change_timer_or_quote(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    harness = build_phase4_harness(qapp, tmp_path, tray_available=True)
    try:
        harness.window.show()
        harness.service.start_focus(focus_draft(harness, ritual=False))
        quote = harness.experience.canvas.quote_label.text()
        harness.window.showMinimized()
        harness.clock.advance_seconds(11)
        harness.coordinator.adapter.poll_once()
        assert harness.coordinator.engine.snapshot().planned_focus_seconds == 11
        assert "00:49 remaining" in (harness.tray.focus_status or "")
        harness.tray.hide_window()
        harness.clock.advance_seconds(3)
        harness.coordinator.adapter.poll_once()
        harness.tray.show_window()
        assert harness.coordinator.engine.snapshot().planned_focus_seconds == 14
        assert harness.experience.canvas.quote_label.text() == quote
    finally:
        harness.close()


def test_ritual_cancel_returns_to_setup_without_ever_starting_engine(
    qapp: QApplication, tmp_path: Path
) -> None:
    harness = build_phase4_harness(qapp, tmp_path)
    try:
        harness.setup.intention_input.setText("Temporary ritual text")
        harness.service.start_focus(
            focus_draft(harness, ritual=True, intention="Temporary ritual text")
        )
        assert not harness.coordinator.has_active_preview
        harness.experience.ritual.cancel()
        assert not harness.service.has_active_session
        assert not harness.window.focus_view_active
        assert harness.setup.intention_input.text() == ""
    finally:
        harness.close()


def test_tray_status_tracks_running_paused_completed_and_overtime(
    qapp: QApplication, tmp_path: Path
) -> None:
    harness = build_phase4_harness(qapp, tmp_path, tray_available=True)
    try:
        harness.service.start_focus(focus_draft(harness, duration=60))
        harness.clock.advance_seconds(18)
        harness.coordinator.adapter.poll_once()
        assert harness.tray.focus_status == "LockIn — 00:42 remaining"
        harness.experience.pause_requested.emit()
        assert harness.tray.focus_status == "LockIn — Paused"
        harness.experience.resume_requested.emit()
        harness.clock.advance_seconds(42)
        harness.coordinator.adapter.poll_once()
        assert harness.tray.focus_status == "LockIn — Planned focus complete"
        harness.experience.overtime_requested.emit()
        harness.clock.advance_seconds(12)
        harness.coordinator.adapter.poll_once()
        assert harness.tray.focus_status == "LockIn — Overtime +00:12"
    finally:
        harness.close()
