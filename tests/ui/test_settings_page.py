from PySide6.QtGui import QKeySequence

from app.services.settings_service import CloseBehavior, SidebarStartup
from app.shortcuts.actions import ShortcutActionId
from app.ui.pages.settings_page import SettingsPage


def test_settings_reflect_changes_and_reset(app_context: object) -> None:
    page = app_context.window.page("settings")  # type: ignore[attr-defined]
    assert isinstance(page, SettingsPage)
    page.sidebar_startup_selector.setCurrentIndex(
        page.sidebar_startup_selector.findData(SidebarStartup.COLLAPSED.value)
    )
    page.minimize_to_tray_checkbox.setChecked(True)
    page.close_behavior_selector.setCurrentIndex(
        page.close_behavior_selector.findData(CloseBehavior.MINIMIZE_TO_TRAY.value)
    )
    settings = app_context.settings  # type: ignore[attr-defined]
    assert settings.sidebar_startup() == SidebarStartup.COLLAPSED
    assert settings.minimize_to_tray()
    assert settings.close_behavior() == CloseBehavior.MINIMIZE_TO_TRAY
    assert page.runtime_path.isReadOnly()
    assert page.portable_path.isReadOnly()

    page.restore_defaults()
    assert settings.theme_id() == "midnight"
    assert settings.sidebar_startup() == SidebarStartup.REMEMBER
    assert not settings.minimize_to_tray()
    assert settings.close_behavior() == CloseBehavior.EXIT


def test_shortcut_rows_conflict_apply_cancel_disable_and_capture(app_context: object) -> None:
    page = app_context.window.page("settings")  # type: ignore[attr-defined]
    assert isinstance(page, SettingsPage)
    assert len(page.shortcut_rows) == 8
    assert not app_context.focus_experience_service.shortcut_manager.active  # type: ignore[attr-defined]
    pause = page.shortcut_rows[ShortcutActionId.PAUSE_RESUME]
    controls = page.shortcut_rows[ShortcutActionId.SHOW_CONTROLS]
    pause.sequence_edit.setKeySequence(QKeySequence("Ctrl+P"))
    page._validate_shortcuts()
    assert page.shortcut_apply_button.isEnabled()
    page.apply_shortcuts()
    service = app_context.shortcut_settings_service  # type: ignore[attr-defined]
    assert service.get(ShortcutActionId.PAUSE_RESUME).key_sequence == "Ctrl+P"
    controls.sequence_edit.setKeySequence(QKeySequence("F11"))
    page._validate_shortcuts()
    assert not page.shortcut_apply_button.isEnabled()
    assert "Toggle full screen" in page.shortcut_message.text()
    page.refresh_shortcuts()
    assert controls.sequence_edit.keySequence().toString() == "C"
    pause.enabled_checkbox.setChecked(False)
    page.apply_shortcuts()
    disabled = service.get(ShortcutActionId.PAUSE_RESUME)
    assert not disabled.enabled and disabled.key_sequence == "Ctrl+P"
    pause.enabled_checkbox.setChecked(True)
    page.apply_shortcuts()
    assert service.get(ShortcutActionId.PAUSE_RESUME).key_sequence == "Ctrl+P"
