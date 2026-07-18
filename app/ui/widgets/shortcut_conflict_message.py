"""Inline validation message for staged shortcut settings."""

from PySide6.QtWidgets import QLabel, QWidget


class ShortcutConflictMessage(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("shortcutConflictMessage")
        self.setWordWrap(True)
        self.setProperty("error", True)
        self.hide()

    def show_message(self, message: str) -> None:
        self.setText(message)
        self.show()

    def clear_message(self) -> None:
        self.clear()
        self.hide()
