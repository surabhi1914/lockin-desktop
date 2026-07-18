from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.services.settings_service import SettingsService
from app.themes.theme_model import Theme
from app.themes.theme_registry import ThemeRegistry
from app.themes.theme_service import ThemeLoadError, ThemeService


def test_apply_all_themes_and_invalid_fallback(qapp: QApplication) -> None:
    service = ThemeService(qapp)
    for theme in service.registry.themes:
        assert service.apply(theme.theme_id) == theme
        assert qapp.styleSheet()
    assert service.apply("invalid").theme_id == "midnight"


def test_saved_invalid_theme_is_corrected(qapp: QApplication, tmp_path: Path) -> None:
    settings = SettingsService(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    settings.set_theme_id("unknown")
    service = ThemeService(qapp)
    assert service.apply_saved(settings).theme_id == "midnight"
    assert settings.theme_id() == "midnight"


def test_missing_requested_file_falls_back_and_missing_default_errors(
    qapp: QApplication, tmp_path: Path
) -> None:
    default_path = tmp_path / "default.qss"
    default_path.write_text("QWidget { color: white; }", encoding="utf-8")
    default = Theme("midnight", "Midnight", True, default_path, "#000", "Default")
    missing = Theme("missing", "Missing", True, tmp_path / "missing.qss", "#111", "Missing")
    service = ThemeService(qapp, ThemeRegistry((default, missing)))
    assert service.apply("missing") == default
    assert service.last_error is not None
    default_path.unlink()
    with pytest.raises(ThemeLoadError, match="default"):
        service.apply("midnight")
