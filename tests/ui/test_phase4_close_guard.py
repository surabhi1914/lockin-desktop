from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.application import ShutdownCoordinator
from app.ui.focus.focus_dialogs import ExitDecision
from tests.phase4_helpers import build_phase4_harness, focus_draft


def test_window_close_and_tray_exit_share_active_session_guard(
    qapp: QApplication, tmp_path: Path
) -> None:
    harness = build_phase4_harness(qapp, tmp_path, tray_available=True)
    shutdown = ShutdownCoordinator(
        qapp,
        harness.window,
        harness.setup._settings,
        harness.connection,  # type: ignore[arg-type]
        harness.tray,
        harness.coordinator,
        harness.service,
    )
    harness.window.set_close_request_handler(shutdown.handle_close_request)
    harness.tray.set_exit_callback(shutdown.request_exit)
    try:
        harness.window.show()
        harness.service.start_focus(focus_draft(harness))
        harness.service._exit_decision_provider = lambda _available: ExitDecision.KEEP_FOCUSING
        harness.tray.request_exit()
        assert harness.service.has_active_session
        assert harness.window.isVisible()

        harness.service._exit_decision_provider = lambda _available: ExitDecision.END_AND_EXIT
        harness.tray.request_exit()
        assert not harness.service.has_active_session
        assert not harness.window.isVisible()
    finally:
        harness.close()
