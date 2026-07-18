from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.services.focus_session_coordinator import FocusSessionCoordinator
from app.services.settings_service import SettingsService
from app.timer import ManualClock
from app.ui.pages.focus_setup_page import FocusSetupPage
from tests.phase3_helpers import isolated_category_service, path_config


def _page(
    tmp_path: Path,
) -> tuple[FocusSetupPage, FocusSessionCoordinator, object]:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    settings = SettingsService(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    coordinator = FocusSessionCoordinator(service, clock_factory=ManualClock)
    return FocusSetupPage(service, settings, coordinator), coordinator, connection


def test_setup_defaults_and_validation(qapp: QApplication, qtbot: object, tmp_path: Path) -> None:
    page, coordinator, connection = _page(tmp_path)
    qtbot.addWidget(page)  # type: ignore[attr-defined]
    try:
        assert (page.duration_input.hours, page.duration_input.minutes) == (0, 50)
        assert page.category_selector.selected_category().category_name == "Other"  # type: ignore[union-attr]
        options = page.options_panel.options()
        assert all(
            (
                options.start_in_fullscreen,
                options.show_quotes,
                options.play_completion_sound,
                options.overtime_enabled,
                options.start_ritual_enabled,
            )
        )
        page.duration_input.set_duration(0, 0)
        assert not page.start_button.isEnabled()
        page.duration_input.set_duration(0, 1)
        assert page.start_button.isEnabled()
        page.intention_input.setText("x" * 241)
        assert not page.start_button.isEnabled()
    finally:
        coordinator.shutdown()
        connection.close()  # type: ignore[attr-defined]


def test_draft_snapshot_and_intention_never_enter_qsettings(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    page, coordinator, connection = _page(tmp_path)
    qtbot.addWidget(page)  # type: ignore[attr-defined]
    try:
        page.intention_input.setText("  Finish the portfolio  ")
        draft = page.build_draft()
        assert draft.temporary_intention == "Finish the portfolio"
        assert (
            draft.category_name_snapshot == page.category_selector.selected_category().category_name
        )  # type: ignore[union-attr]
        page._remember_safe_defaults(draft)
        settings = page._settings.qsettings
        assert all("intention" not in key.casefold() for key in settings.allKeys())
        assert "Finish the portfolio" not in str(settings.value("focus_setup/last_category_id"))
    finally:
        coordinator.shutdown()
        connection.close()  # type: ignore[attr-defined]


def test_navigation_preserves_unsent_form_values(app_context: object) -> None:
    window = app_context.window  # type: ignore[attr-defined]
    page = window.page("focus_setup")
    assert isinstance(page, FocusSetupPage)
    page.intention_input.setText("Keep this while navigating")
    page.duration_input.set_duration(1, 5)
    window.navigate("categories")
    window.navigate("focus_setup")
    assert page.intention_input.text() == "Keep this while navigating"
    assert (page.duration_input.hours, page.duration_input.minutes) == (1, 5)
