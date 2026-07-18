"""Final local session summary presentation."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.models.focus_summary import FocusSummary
from app.ui.focus.focus_canvas import format_focus_time
from app.ui.focus.focus_style import enforce_black_background


class SessionSummaryOverlay(QWidget):
    return_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("focusOverlay")
        enforce_black_background(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.addStretch(1)
        title = QLabel("SESSION SUMMARY")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPixelSize(42)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        form = QFormLayout()
        self.values: dict[str, QLabel] = {}
        for key, label in (
            ("category", "Category"),
            ("started", "Started"),
            ("ended", "Ended"),
            ("planned", "Planned duration"),
            ("planned_focus", "Planned focus completed"),
            ("overtime", "Overtime"),
            ("total", "Total focused time"),
            ("paused", "Total paused time"),
            ("pause_count", "Pause count"),
            ("longest", "Longest continuous block"),
            ("average", "Average continuous block"),
            ("blocks", "Continuous blocks"),
            ("distractions", "Distractions marked"),
            ("status", "Status"),
            ("saved", "Storage"),
            ("sync", "Portable sync"),
        ):
            value = QLabel()
            self.values[key] = value
            form.addRow(label, value)
        layout.addLayout(form)
        self.return_button = QPushButton("Return to Setup")
        self.return_button.setAccessibleName("Return to focus setup and discard summary")
        self.return_button.clicked.connect(self.return_requested.emit)
        layout.addWidget(self.return_button)
        layout.addStretch(1)

    def present(self, summary: FocusSummary) -> None:
        self.values["category"].setText(summary.category_name)
        self.values["started"].setText(summary.started_at_local or "—")
        self.values["ended"].setText(summary.ended_at_local or "—")
        self.values["planned"].setText(format_focus_time(summary.planned_duration_seconds))
        self.values["planned_focus"].setText(format_focus_time(summary.planned_focus_seconds))
        self.values["overtime"].setText(format_focus_time(summary.overtime_seconds))
        self.values["total"].setText(format_focus_time(summary.total_focus_seconds))
        self.values["paused"].setText(format_focus_time(summary.total_pause_seconds))
        self.values["pause_count"].setText(str(summary.pause_count))
        self.values["longest"].setText(format_focus_time(summary.longest_continuous_seconds))
        self.values["average"].setText(format_focus_time(summary.average_continuous_seconds))
        self.values["blocks"].setText(str(summary.continuous_block_count))
        self.values["distractions"].setText(str(summary.distraction_count))
        self.values["status"].setText(summary.status.value)
        self.values["saved"].setText("Saved locally" if summary.saved_locally else "Not saved")
        self.values["sync"].setText(summary.sync_message)
