import sqlite3
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.application import ApplicationStartupError, create_application
from app.bootstrap import run_phase0_bootstrap
from app.core.paths import PathConfig
from app.services.settings_service import SettingsService


def _portable_bytes(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_application_starts_without_data_mutation(
    qapp: QApplication, qtbot: object, isolated_config: PathConfig, tmp_path: Path
) -> None:
    assert run_phase0_bootstrap(config=isolated_config).success
    before = _portable_bytes(isolated_config.portable_root)
    settings = SettingsService(QSettings(str(tmp_path / "startup.ini"), QSettings.Format.IniFormat))
    context = create_application(
        config=isolated_config, settings=settings, tray_available=False, show_window=False
    )
    qtbot.addWidget(context.window)  # type: ignore[attr-defined]
    assert context.window.windowTitle() == "LockIn"
    assert context.window.current_page_id == "home"
    assert context.connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    assert _portable_bytes(isolated_config.portable_root) == before
    assert not list((isolated_config.portable_root / "sessions").rglob("*.csv"))
    context.shutdown()


def test_shutdown_closes_database(app_context: object) -> None:
    connection = app_context.connection  # type: ignore[attr-defined]
    app_context.shutdown()  # type: ignore[attr-defined]
    assert app_context.shutdown_coordinator.shutdown_complete  # type: ignore[attr-defined]
    try:
        connection.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        pass
    else:  # pragma: no cover - documents the required sqlite behavior
        raise AssertionError("Shutdown did not close SQLite")


def test_invalid_portable_data_stops_startup_without_reset(
    qapp: QApplication, isolated_config: PathConfig, tmp_path: Path
) -> None:
    assert run_phase0_bootstrap(config=isolated_config).success
    categories = isolated_config.portable_root / "categories.csv"
    categories.write_text("bad,header\npersonal,data\n", encoding="utf-8")
    original = categories.read_bytes()
    settings = SettingsService(QSettings(str(tmp_path / "failure.ini"), QSettings.Format.IniFormat))
    with pytest.raises(ApplicationStartupError, match="header"):
        create_application(config=isolated_config, settings=settings, tray_available=False)
    assert categories.read_bytes() == original
