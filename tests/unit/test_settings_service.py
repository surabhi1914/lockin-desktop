from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings

from app.services.settings_service import CloseBehavior, SettingsService, SidebarStartup


def _service(path: Path) -> SettingsService:
    return SettingsService(QSettings(str(path), QSettings.Format.IniFormat))


def test_defaults_and_typed_set_get(tmp_path: Path) -> None:
    service = _service(tmp_path / "settings.ini")
    service.reset_phase1_defaults()
    assert service.theme_id() == "midnight"
    assert service.geometry() is None
    assert service.window_state() is None
    assert not service.sidebar_collapsed()
    assert service.sidebar_startup() == SidebarStartup.REMEMBER
    assert not service.minimize_to_tray()
    assert service.close_behavior() == CloseBehavior.EXIT
    assert service.last_page_id() == "home"

    service.set_theme_id("forest")
    service.set_geometry(QByteArray(b"geometry"))
    service.set_window_state(QByteArray(b"state"))
    service.set_sidebar_collapsed(True)
    service.set_sidebar_startup(SidebarStartup.COLLAPSED)
    service.set_minimize_to_tray(True)
    service.set_close_behavior(CloseBehavior.MINIMIZE_TO_TRAY)
    service.set_last_page_id("quotes")
    service.sync()
    assert service.theme_id() == "forest"
    assert service.geometry() == QByteArray(b"geometry")
    assert service.window_state() == QByteArray(b"state")
    assert service.sidebar_collapsed()
    assert service.sidebar_startup() == SidebarStartup.COLLAPSED
    assert service.minimize_to_tray()
    assert service.close_behavior() == CloseBehavior.MINIMIZE_TO_TRAY
    assert service.last_page_id() == "quotes"


def test_invalid_values_fall_back_safely(tmp_path: Path) -> None:
    service = _service(tmp_path / "invalid.ini")
    raw = service.qsettings
    raw.setValue("ui/theme_id", "")
    raw.setValue("window/geometry", "not geometry")
    raw.setValue("sidebar/collapsed", "maybe")
    raw.setValue("sidebar/startup", "sideways")
    raw.setValue("tray/minimize_to_tray", "no")
    raw.setValue("window/close_behavior", "hide_forever")
    raw.setValue("navigation/last_page", "unknown")
    assert service.theme_id() == "midnight"
    assert service.geometry() is None
    assert not service.sidebar_collapsed()
    assert service.sidebar_startup() == SidebarStartup.REMEMBER
    assert not service.minimize_to_tray()
    assert service.close_behavior() == CloseBehavior.EXIT
    assert service.last_page_id() == "home"


def test_reset_and_file_isolation(tmp_path: Path) -> None:
    first = _service(tmp_path / "first.ini")
    second = _service(tmp_path / "second.ini")
    first.set_theme_id("light")
    first.sync()
    assert second.theme_id() == "midnight"
    first.reset_phase1_defaults()
    assert first.theme_id() == "midnight"


def test_invalid_page_is_never_stored(tmp_path: Path) -> None:
    service = _service(tmp_path / "page.ini")
    service.set_last_page_id("not-real")
    assert service.last_page_id() == "home"


def test_environment_can_isolate_default_qsettings(monkeypatch, tmp_path) -> None:
    path = tmp_path / "isolated-settings.ini"
    monkeypatch.setenv("LOCKIN_SETTINGS_PATH", str(path))
    service = SettingsService()
    service.set_theme_id("forest")
    service.sync()
    assert path.exists()
    assert SettingsService().theme_id() == "forest"
