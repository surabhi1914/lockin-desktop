"""Review verified source counts before a destructive import."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.portability.import_models import ImportReadinessReport


class ImportPreviewDialog(QDialog):
    def __init__(self, report: ImportReadinessReport, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Review portable import")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Review verified portable history before staging the database."))
        details = QPlainTextEdit()
        details.setReadOnly(True)
        summary = report.summary
        lines: list[str] = []
        if summary is not None:
            lines.extend(
                (
                    f"Portable root: {summary.portable_root}",
                    f"Sessions: {summary.counts.sessions}",
                    f"Segments: {summary.counts.logical_segments}",
                    f"Distractions: {summary.counts.distractions}",
                    f"Categories: {summary.counts.categories}",
                    f"Goals: {summary.counts.goals}",
                    f"Quotes: {summary.counts.quotes}",
                    f"Devices: {summary.counts.devices}",
                    f"Date range: {summary.earliest_local_date or '-'} to "
                    f"{summary.latest_local_date or '-'}",
                )
            )
        lines.append(f"Warnings: {len(report.warnings)}")
        lines.append(f"Conflicts: {len(report.conflicts)}")
        details.setPlainText("\n".join(lines))
        layout.addWidget(details)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
