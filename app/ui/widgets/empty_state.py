"""Intentional zero-data state with an optional disabled future action."""

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


class EmptyState(QFrame):
    def __init__(
        self,
        title: str,
        description: str,
        action_text: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setObjectName("emptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 17px; font-weight: 600;")
        self.description_label = QLabel(description)
        self.description_label.setProperty("muted", True)
        self.description_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        self.action_button: QPushButton | None = None
        if action_text:
            self.action_button = QPushButton(action_text)
            self.action_button.setEnabled(False)
            self.action_button.setToolTip("Available in a later phase")
            layout.addWidget(self.action_button)
