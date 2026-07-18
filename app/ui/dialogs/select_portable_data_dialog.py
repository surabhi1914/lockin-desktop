"""Native portable-folder selection helper."""

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget


def select_portable_data_folder(parent: QWidget | None, initial: Path) -> Path | None:
    selected = QFileDialog.getExistingDirectory(
        parent,
        "Use Existing Portable Data",
        str(initial),
        QFileDialog.Option.ShowDirsOnly,
    )
    return None if not selected else Path(selected)
