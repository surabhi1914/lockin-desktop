"""Reusable placeholder metric card with no fabricated values."""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class MetricCard(QFrame):
    def __init__(
        self,
        label: str,
        value: str = "—",
        supporting_text: str = "Available after session tracking is implemented.",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setAccessibleName(f"{label} metric")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(7)
        self.label = QLabel(label)
        self.label.setProperty("muted", True)
        self.value = QLabel(value)
        self.value.setObjectName("metricValue")
        self.value.setStyleSheet("font-size: 24px; font-weight: 650;")
        self.supporting_text = QLabel(supporting_text)
        self.supporting_text.setProperty("muted", True)
        self.supporting_text.setWordWrap(True)
        layout.addWidget(self.label)
        layout.addWidget(self.value)
        layout.addWidget(self.supporting_text)
