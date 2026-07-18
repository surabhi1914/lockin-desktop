from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.timer.enums import TimerState
from app.ui.focus.focus_dialogs import ExitDecision, StopDecision
from tests.phase4_helpers import build_phase4_harness, focus_draft


def test_stop_cancel_then_review_and_active_exit_choices(
    qapp: QApplication, tmp_path: Path
) -> None:
    harness = build_phase4_harness(
        qapp,
        tmp_path,
        tray_available=True,
        stop_decision=StopDecision.CONTINUE,
    )
    try:
        harness.window.show()
        harness.service.start_focus(focus_draft(harness))
        assert not harness.service.request_stop()
        assert harness.coordinator.has_active_preview
        harness.service._stop_decision_provider = lambda: StopDecision.STOP_AND_REVIEW
        assert harness.service.request_stop()
        harness.service.return_to_setup()

        harness.service.start_focus(focus_draft(harness))
        harness.service._exit_decision_provider = lambda _available: ExitDecision.KEEP_FOCUSING
        assert not harness.service.request_close()
        assert harness.service.has_active_session
        harness.service._exit_decision_provider = lambda _available: ExitDecision.MINIMIZE_TO_TRAY
        assert not harness.service.request_close()
        assert not harness.window.isVisible()
        harness.tray.show_window()
        harness.service._exit_decision_provider = lambda _available: ExitDecision.END_AND_EXIT
        assert harness.service.request_close()
        assert not harness.service.has_active_session
    finally:
        harness.close()


@pytest.mark.parametrize("stage", ["ritual", "running", "paused", "completed", "overtime"])
def test_keep_focusing_preserves_every_guarded_stage(
    qapp: QApplication, tmp_path: Path, stage: str
) -> None:
    harness = build_phase4_harness(
        qapp,
        tmp_path,
        exit_decision=ExitDecision.KEEP_FOCUSING,
    )
    try:
        draft = focus_draft(harness, duration=2, ritual=stage == "ritual")
        harness.service.start_focus(draft)
        if stage == "ritual":
            assert not harness.coordinator.has_active_preview
        elif stage == "paused":
            harness.coordinator.pause()
            assert harness.coordinator.engine.state is TimerState.PAUSED
        elif stage in {"completed", "overtime"}:
            harness.clock.advance_seconds(2)
            harness.coordinator.adapter.poll_once()
            assert harness.coordinator.engine.state is TimerState.COMPLETED
            if stage == "overtime":
                harness.coordinator.start_overtime()
                assert harness.coordinator.engine.state is TimerState.OVERTIME
        assert not harness.service.request_close()
        assert harness.service.has_active_session
    finally:
        harness.close()
