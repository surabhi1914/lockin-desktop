from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from app.services.focus_session_coordinator import FocusSessionCoordinator
from app.services.settings_service import SettingsService
from app.timer import ManualClock, TimerState
from app.ui.pages.focus_setup_page import FocusSetupPage
from tests.phase3_helpers import isolated_category_service, path_config


def test_preview_uses_real_timer_controls_overtime_and_clears_intention(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    clock = ManualClock()
    coordinator = FocusSessionCoordinator(service, clock_factory=lambda: clock)
    settings = SettingsService(QSettings(str(tmp_path / "preview.ini"), QSettings.Format.IniFormat))
    page = FocusSetupPage(service, settings, coordinator)
    qtbot.addWidget(page)  # type: ignore[attr-defined]
    try:
        page.duration_input.set_duration(0, 1)
        page.intention_input.setText("Temporary only")
        qtbot.mouseClick(page.start_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert coordinator.engine.state is TimerState.RUNNING
        assert page.stack.currentWidget() is page.preview_widget
        assert page.preview_intention.text() == "Temporary only"
        clock.advance_seconds(5)
        coordinator.adapter.poll_once()
        qtbot.mouseClick(page.pause_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert coordinator.engine.state is TimerState.PAUSED
        qtbot.mouseClick(page.resume_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        clock.advance_seconds(55)
        coordinator.adapter.poll_once()
        assert coordinator.engine.state is TimerState.COMPLETED
        assert page.overtime_button.isEnabled()
        qtbot.mouseClick(page.overtime_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        clock.advance_seconds(2)
        coordinator.adapter.poll_once()
        assert coordinator.engine.snapshot().overtime_seconds == 2
        qtbot.mouseClick(page.stop_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert coordinator.current_context is None
        assert page.stack.currentWidget() is page.setup_widget
        assert page.intention_input.text() == ""
    finally:
        coordinator.shutdown()
        connection.close()


def test_preview_does_not_activate_later_phase_behavior(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    coordinator = FocusSessionCoordinator(service, clock_factory=ManualClock)
    page = FocusSetupPage(
        service,
        SettingsService(QSettings(str(tmp_path / "later.ini"), QSettings.Format.IniFormat)),
        coordinator,
    )
    qtbot.addWidget(page)  # type: ignore[attr-defined]
    try:
        page.duration_input.set_duration(0, 1)
        page.start_button.click()
        assert not page.window().isFullScreen()
        text = page.preview_widget.findChildren(type(page.preview_state))
        assert any("No full screen" in label.text() for label in text)
    finally:
        coordinator.shutdown()
        connection.close()
