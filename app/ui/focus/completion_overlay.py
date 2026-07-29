"""Exactly-once planned-completion overlay presentation."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.timer.models import TimerSnapshot
from app.ui.focus.focus_canvas import format_focus_time
from app.ui.focus.focus_style import enforce_black_background


class CompletionOverlay(QWidget):
    finish_requested = Signal()
    overtime_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("focusOverlay")
        enforce_black_background(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.addStretch(1)
        title = QLabel("LOCK-IN COMPLETE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPixelSize(48)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        metrics = QFormLayout()
        metrics.setHorizontalSpacing(24)
        self.planned_value = QLabel()
        self.total_value = QLabel()
        self.longest_value = QLabel()
        metrics.addRow("Planned focus", self.planned_value)
        metrics.addRow("Current total focus", self.total_value)
        metrics.addRow("Longest continuous block", self.longest_value)
        layout.addLayout(metrics)
        self.finish_button = QPushButton("Finish Session")
        self.finish_button.setAccessibleName("Finish completed focus session")
        self.finish_button.clicked.connect(self.finish_requested.emit)
        self.overtime_button = QPushButton("Continue Overtime")
        self.overtime_button.setAccessibleName("Continue explicit overtime")
        self.overtime_button.clicked.connect(self.overtime_requested.emit)
        layout.addWidget(self.finish_button)
        layout.addWidget(self.overtime_button)
        saved = QLabel("Your completed focus time has been saved locally.")
        saved.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(saved)
        layout.addStretch(1)

    def present(self, snapshot: TimerSnapshot, *, overtime_enabled: bool) -> None:
        self.planned_value.setText(format_focus_time(snapshot.planned_duration_seconds))
        self.total_value.setText(format_focus_time(snapshot.total_focus_seconds))
        self.longest_value.setText(format_focus_time(snapshot.longest_continuous_seconds))
        self.overtime_button.setVisible(overtime_enabled and snapshot.can_start_overtime)
