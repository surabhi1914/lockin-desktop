"""Release identity and local-data access without network dependencies."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.resources import ResourceLocator
from app.version import PUBLISHER, __version__


def _build_identifier() -> str:
    path = ResourceLocator.standard().optional("build_commit.txt")
    if path is None:
        return "development"
    value = path.read_text(encoding="utf-8").strip()
    return value[:40] if value else "unknown"


class AboutDialog(QDialog):
    def __init__(
        self, runtime_root: Path, portable_root: Path, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About LockIn {__version__}")
        layout = QVBoxLayout(self)
        heading = QLabel(f"LockIn {__version__}")
        heading.setProperty("heading", True)
        layout.addWidget(heading)
        details = QLabel(
            "Local-first focus timer\n"
            f"Author and publisher: {PUBLISHER}\n"
            "License: MIT\n"
            f"Build: {_build_identifier()}\n\n"
            "LockIn has no telemetry and requires no cloud account."
        )
        details.setWordWrap(True)
        layout.addWidget(details)
        runtime_button = QPushButton("Open Runtime Data Folder")
        portable_button = QPushButton("Open Portable Data Folder")
        runtime_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(runtime_root)))
        )
        portable_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(portable_root)))
        )
        layout.addWidget(runtime_button)
        layout.addWidget(portable_button)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)
