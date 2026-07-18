from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.application import ApplicationContext, create_application
from app.core.paths import PathConfig
from app.services.settings_service import SettingsService


@pytest.fixture
def isolated_settings(tmp_path: Path) -> SettingsService:
    settings = QSettings(str(tmp_path / "ui-settings.ini"), QSettings.Format.IniFormat)
    settings.clear()
    return SettingsService(settings)


@pytest.fixture
def app_context(
    qapp: QApplication,
    qtbot: object,
    isolated_config: PathConfig,
    isolated_settings: SettingsService,
) -> Iterator[ApplicationContext]:
    context = create_application(
        config=isolated_config,
        settings=isolated_settings,
        tray_available=False,
        show_window=False,
    )
    qtbot.addWidget(context.window)  # type: ignore[attr-defined]
    yield context
    context.window.hide()
    context.shutdown()
