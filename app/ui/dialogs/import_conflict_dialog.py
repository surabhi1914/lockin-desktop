"""Explicit abort/skip choice for portable conflicts."""

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from app.portability.import_models import ImportConflict


class ImportConflictDialog(QDialog):
    SKIP_CONFLICTS = 2
    EXPORT_REPORT = 3

    def __init__(
        self, conflicts: tuple[ImportConflict, ...], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Portable import conflicts")
        layout = QVBoxLayout(self)
        message = QLabel(
            f"{len(conflicts)} conflict(s) cannot be overwritten automatically. "
            "Abort, or explicitly import independent safe records and skip conflicts."
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        self.abort_button = QPushButton("Abort Import")
        self.skip_button = QPushButton("Import Safe Records / Skip Conflicts")
        self.export_button = QPushButton("Export Conflict Report")
        self.abort_button.clicked.connect(self.reject)
        self.skip_button.clicked.connect(lambda: self.done(self.SKIP_CONFLICTS))
        self.export_button.clicked.connect(lambda: self.done(self.EXPORT_REPORT))
        layout.addWidget(self.abort_button)
        layout.addWidget(self.skip_button)
        layout.addWidget(self.export_button)
