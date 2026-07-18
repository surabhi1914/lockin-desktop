"""Reusable accessible inline validation label."""

from PySide6.QtWidgets import QLabel, QWidget


class ValidationMessage(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("validationMessage")
        self.setProperty("validation", True)
        self.setWordWrap(True)
        self.setAccessibleName("Validation message")
        self.clear_error()

    def set_error(self, message: str) -> None:
        self.setText(message)
        self.setVisible(bool(message))

    def clear_error(self) -> None:
        self.clear()
        self.setVisible(False)
