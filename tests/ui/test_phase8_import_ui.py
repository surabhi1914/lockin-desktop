from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QPlainTextEdit

from app.portability.import_models import (
    EntityCounts,
    ImportConflict,
    ImportReadinessReport,
    SourceSummary,
)
from app.services.settings_service import SettingsService
from app.services.shortcut_settings_service import ShortcutSettingsService
from app.themes.theme_service import ThemeService
from app.ui.dialogs.import_conflict_dialog import ImportConflictDialog
from app.ui.dialogs.import_preview_dialog import ImportPreviewDialog
from app.ui.pages.settings_page import SettingsPage


def test_preview_and_conflict_dialogs_show_explicit_actions(qapp, qtbot, tmp_path: Path) -> None:
    summary = SourceSummary(
        tmp_path, EntityCounts(sessions=3, logical_segments=4), None, None, (), 8
    )
    report = ImportReadinessReport(True, summary)
    preview = ImportPreviewDialog(report)
    qtbot.addWidget(preview)
    assert "Sessions: 3" in preview.findChild(QPlainTextEdit).toPlainText()
    conflict = ImportConflict("sessions", "id", "different", None, {}, {})
    dialog = ImportConflictDialog((conflict,))
    qtbot.addWidget(dialog)
    assert dialog.abort_button.text() == "Abort Import"
    assert "Skip Conflicts" in dialog.skip_button.text()
    assert dialog.export_button.text() == "Export Conflict Report"


def test_settings_exposes_folder_and_import_actions(qapp, qtbot, tmp_path: Path) -> None:
    settings = SettingsService(QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat))
    shortcut = ShortcutSettingsService(settings.qsettings)
    theme = ThemeService(qapp)
    page = SettingsPage(settings, shortcut, theme, tmp_path / "runtime", tmp_path / "portable")
    qtbot.addWidget(page)
    assert page.use_portable_button.text() == "Use Existing Portable Data"
    assert page.import_history_button.text() == "Import Portable History"
