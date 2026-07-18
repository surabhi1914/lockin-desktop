from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from app.services.shortcut_settings_service import ShortcutSettingsService
from app.shortcuts.actions import ShortcutActionId
from app.shortcuts.errors import ShortcutConflictError


def service_at(path: Path) -> ShortcutSettingsService:
    return ShortcutSettingsService(QSettings(str(path), QSettings.Format.IniFormat))


def test_defaults_save_reload_disable_reenable_and_reset(tmp_path: Path) -> None:
    path = tmp_path / "shortcuts.ini"
    service = service_at(path)
    defaults = service.get_all()
    assert len(defaults) == 8 and all(item.is_default for item in defaults)
    custom = tuple(
        service.validator.make_binding(item.action_id, "Ctrl+P", item.enabled)
        if item.action_id is ShortcutActionId.PAUSE_RESUME
        else item
        for item in defaults
    )
    saved = service.save_all(custom)
    assert service_at(path).get(ShortcutActionId.PAUSE_RESUME).key_sequence == "Ctrl+P"
    disabled = tuple(
        replace(item, enabled=False) if item.action_id is ShortcutActionId.PAUSE_RESUME else item
        for item in saved
    )
    service.save_all(disabled)
    retained = service_at(path).get(ShortcutActionId.PAUSE_RESUME)
    assert not retained.enabled and retained.key_sequence == "Ctrl+P"
    service.save_all(
        tuple(replace(item, enabled=True) if not item.enabled else item for item in disabled)
    )
    assert service.get(ShortcutActionId.PAUSE_RESUME).key_sequence == "Ctrl+P"
    service.reset_one(ShortcutActionId.PAUSE_RESUME)
    assert service.get(ShortcutActionId.PAUSE_RESUME).key_sequence == "Space"
    service.save_all(custom)
    assert all(item.is_default for item in service.reset_all())


def test_invalid_save_never_changes_existing_settings(tmp_path: Path) -> None:
    service = service_at(tmp_path / "atomic.ini")
    before = service.save_all(service.get_all())
    conflict = list(before)
    conflict[6] = service.validator.make_binding(ShortcutActionId.SHOW_CONTROLS, "F11", True)
    with pytest.raises(ShortcutConflictError):
        service.save_all(tuple(conflict))
    assert service.get_all() == before


def test_corrupt_conflicts_recover_defaults_and_keep_other_custom_values(tmp_path: Path) -> None:
    service = service_at(tmp_path / "corrupt.ini")
    raw = service.qsettings
    raw.setValue("shortcuts/pause_resume/key", "F11")
    raw.setValue("shortcuts/toggle_fullscreen/key", "F11")
    raw.setValue("shortcuts/mark_distraction/key", "Z")
    raw.setValue("shortcuts/stop_session/key", "S")
    bindings = service.get_all()
    by_id = {item.action_id: item for item in bindings}
    assert by_id[ShortcutActionId.PAUSE_RESUME].key_sequence == "Space"
    assert by_id[ShortcutActionId.TOGGLE_FULLSCREEN].key_sequence == "F11"
    assert by_id[ShortcutActionId.MARK_DISTRACTION].key_sequence == "Z"
    assert by_id[ShortcutActionId.STOP_SESSION].key_sequence == "Ctrl+Shift+S"
    assert service.warnings
    assert not (tmp_path / "sessions").exists()
    assert not (tmp_path / "distractions").exists()


def test_boolean_migration_and_failed_sync_restore_previous_values(tmp_path: Path) -> None:
    class FailingSettings(QSettings):
        def __init__(self, path: str) -> None:
            super().__init__(path, QSettings.Format.IniFormat)
            self.fail_next_sync = False

        def sync(self) -> None:
            if self.fail_next_sync:
                self.fail_next_sync = False
                raise OSError("simulated settings failure")
            super().sync()

    settings = FailingSettings(str(tmp_path / "failure.ini"))
    settings.setValue("shortcuts/pause_resume/enabled", "no")
    settings.setValue("shortcuts/toggle_fullscreen/enabled", 1)
    settings.setValue("shortcuts/exit_fullscreen/enabled", "maybe")
    service = ShortcutSettingsService(settings)
    loaded = {item.action_id: item for item in service.get_all()}
    assert not loaded[ShortcutActionId.PAUSE_RESUME].enabled
    assert loaded[ShortcutActionId.TOGGLE_FULLSCREEN].enabled
    assert loaded[ShortcutActionId.EXIT_FULLSCREEN].enabled
    before = service.get_all()
    changed = tuple(
        service.validator.make_binding(item.action_id, "Ctrl+P", True)
        if item.action_id is ShortcutActionId.PAUSE_RESUME
        else item
        for item in before
    )
    settings.fail_next_sync = True
    with pytest.raises(OSError):
        service.save_all(changed)
    assert service.get_all() == before
