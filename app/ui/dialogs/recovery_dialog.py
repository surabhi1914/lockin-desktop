"""Confirmed-time recovery choice and privacy-safe detail views."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.recovery.models import RecoveryAnalysis


class RecoveryDialog(QDialog):
    SAVE_CONFIRMED = 2
    DISCARD = 3
    REVIEW = 4
    EXIT = 5

    def __init__(self, analysis: RecoveryAnalysis, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.analysis = analysis
        self.setWindowTitle("Recover unfinished focus session")
        layout = QVBoxLayout(self)
        heading = QLabel(f"Unfinished session: {analysis.category_name}")
        heading.setProperty("heading", True)
        layout.addWidget(heading)
        summary = QLabel(
            f"Confirmed focus: {analysis.confirmed_focus_seconds} seconds\n"
            f"Unknown time excluded: {analysis.unknown_gap_seconds} seconds\n"
            f"Last reliable boundary: {analysis.confirmed_boundary_at_utc}"
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)
        note = QLabel(
            "LockIn will never count time after the last reliable heartbeat. "
            "You can save confirmed time or discard this session without deleting its audit."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox()
        save = buttons.addButton("Save Confirmed Time", QDialogButtonBox.ButtonRole.AcceptRole)
        discard = buttons.addButton("Discard Session", QDialogButtonBox.ButtonRole.DestructiveRole)
        review = buttons.addButton("Review Details", QDialogButtonBox.ButtonRole.ActionRole)
        exit_button = buttons.addButton("Exit", QDialogButtonBox.ButtonRole.RejectRole)
        assert isinstance(save, QPushButton)
        assert isinstance(discard, QPushButton)
        assert isinstance(review, QPushButton)
        assert isinstance(exit_button, QPushButton)
        save.clicked.connect(lambda: self.done(self.SAVE_CONFIRMED))
        discard.clicked.connect(lambda: self.done(self.DISCARD))
        review.clicked.connect(lambda: self.done(self.REVIEW))
        exit_button.clicked.connect(lambda: self.done(self.EXIT))
        layout.addWidget(buttons)


class RecoveredSessionReviewDialog(QDialog):
    def __init__(self, analysis: RecoveryAnalysis, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recovery details")
        layout = QVBoxLayout(self)
        details = QLabel(
            "\n".join(
                (
                    f"Session: {analysis.session_id}",
                    f"Original state: {analysis.original_timer_state}",
                    f"Planned focus: {analysis.planned_focus_seconds}s",
                    f"Confirmed planned: {analysis.confirmed_planned_focus_seconds}s",
                    f"Confirmed overtime: {analysis.confirmed_overtime_seconds}s",
                    f"Confirmed pause: {analysis.confirmed_pause_seconds}s",
                    f"Unknown window: {analysis.unknown_gap_seconds}s (excluded)",
                    f"Open segment: {analysis.open_segment_type or 'none'}",
                    f"Warnings: {'; '.join(analysis.warnings) or 'none'}",
                )
            )
        )
        details.setTextInteractionFlags(details.textInteractionFlags())
        details.setWordWrap(True)
        layout.addWidget(details)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)
