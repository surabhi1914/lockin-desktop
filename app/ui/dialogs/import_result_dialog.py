"""Friendly local result presentation without raw tracebacks."""

from PySide6.QtWidgets import QMessageBox, QWidget

from app.portability.import_models import ImportResult


def show_import_result(result: ImportResult, parent: QWidget | None = None) -> None:
    if result.success:
        QMessageBox.information(
            parent,
            "Portable import complete",
            f"Imported {result.inserted} record(s); skipped {result.skipped}.\n\n"
            "Restart LockIn to reopen services on the promoted database.",
        )
    else:
        QMessageBox.warning(
            parent,
            "Portable import not completed",
            "\n".join(result.errors) or "The import was cancelled or blocked by conflicts.",
        )
