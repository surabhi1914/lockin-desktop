from pathlib import Path

from PySide6.QtWidgets import QLabel, QPushButton

from app.core.resources import ResourceLocator
from app.ui.dialogs import about_dialog
from app.ui.dialogs.about_dialog import AboutDialog


def test_about_dialog_has_release_privacy_and_data_folder_actions(qtbot, tmp_path: Path) -> None:
    dialog = AboutDialog(tmp_path / "runtime", tmp_path / "portable")
    qtbot.addWidget(dialog)
    text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    assert "LockIn 1.1.1" in text
    assert "Surabhi Nair" in text
    assert "no telemetry" in text
    buttons = {button.text() for button in dialog.findChildren(QPushButton)}
    assert "Open Runtime Data Folder" in buttons
    assert "Open Portable Data Folder" in buttons


def test_about_build_identifier_reads_sanitized_bundle_metadata(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "build_commit.txt").write_text("abcdef123456\n", encoding="utf-8")
    monkeypatch.setattr(
        ResourceLocator, "standard", classmethod(lambda cls: ResourceLocator(tmp_path))
    )
    assert about_dialog._build_identifier() == "abcdef123456"
