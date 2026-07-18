"""Non-blocking breath, intention, countdown, and fade ritual."""

from dataclasses import dataclass

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.focus.focus_style import enforce_black_background


@dataclass(frozen=True, slots=True)
class RitualDurations:
    breath_ms: int = 1800
    intention_ms: int = 1000
    countdown_ms: int = 700
    fade_ms: int = 500

    def __post_init__(self) -> None:
        if min(self.breath_ms, self.intention_ms, self.countdown_ms, self.fade_ms) < 0:
            raise ValueError("ritual durations cannot be negative")


class StartRitual(QWidget):
    completed = Signal()
    cancelled = Signal()

    def __init__(
        self,
        *,
        durations: RitualDurations | None = None,
        reduced_motion: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("startRitual")
        enforce_black_background(self)
        self._durations = durations or RitualDurations()
        self._reduced_motion = reduced_motion
        self._steps: list[tuple[str, int]] = []
        self._step_index = 0
        self._active = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._fade.finished.connect(self._complete)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(22)
        layout.addStretch(1)
        self.prompt_label = QLabel("Take one slow breath.")
        self.prompt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prompt_font = self.prompt_label.font()
        prompt_font.setPixelSize(34)
        self.prompt_label.setFont(prompt_font)
        layout.addWidget(self.prompt_label)
        self.intention_heading = QLabel("Your intention:")
        self.intention_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.intention_heading)
        self.intention_label = QLabel()
        self.intention_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.intention_label.setWordWrap(True)
        intention_font = self.intention_label.font()
        intention_font.setPixelSize(24)
        self.intention_label.setFont(intention_font)
        layout.addWidget(self.intention_label)
        self.countdown_label = QLabel()
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        countdown_font = self.countdown_label.font()
        countdown_font.setPixelSize(120)
        self.countdown_label.setFont(countdown_font)
        layout.addWidget(self.countdown_label)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setAccessibleName("Cancel start ritual")
        self.cancel_button.setToolTip("Cancel and return to focus setup")
        self.cancel_button.clicked.connect(self.cancel)
        layout.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

    @property
    def active(self) -> bool:
        return self._active

    def start(self, intention: str | None) -> None:
        self._timer.stop()
        self._fade.stop()
        self._opacity.setOpacity(1.0)
        self._active = True
        self._step_index = 0
        has_intention = bool(intention)
        self.intention_heading.setVisible(has_intention)
        self.intention_label.setVisible(has_intention)
        self.intention_label.setText(intention or "")
        self._steps = [
            ("breath", self._durations.breath_ms),
            ("intention", self._durations.intention_ms),
            ("3", self._durations.countdown_ms),
            ("2", self._durations.countdown_ms),
            ("1", self._durations.countdown_ms),
        ]
        self._show_step()

    def cancel(self) -> None:
        if not self._active:
            return
        self._active = False
        self._timer.stop()
        self._fade.stop()
        self.cancelled.emit()

    def shutdown(self) -> None:
        self._active = False
        self._timer.stop()
        self._fade.stop()
        self.intention_label.clear()

    def _show_step(self) -> None:
        if not self._active:
            return
        name, duration = self._steps[self._step_index]
        self.prompt_label.setVisible(name == "breath")
        self.intention_heading.setVisible(name == "intention" and bool(self.intention_label.text()))
        self.intention_label.setVisible(name == "intention" and bool(self.intention_label.text()))
        self.countdown_label.setText(name if name in {"3", "2", "1"} else "")
        self.countdown_label.setVisible(bool(self.countdown_label.text()))
        self._timer.start(duration)

    def _advance(self) -> None:
        if not self._active:
            return
        self._step_index += 1
        if self._step_index < len(self._steps):
            self._show_step()
            return
        if self._reduced_motion or self._durations.fade_ms == 0:
            QTimer.singleShot(0, self._complete)
            return
        self._fade.setDuration(self._durations.fade_ms)
        self._fade.start()

    def _complete(self) -> None:
        if not self._active:
            return
        self._active = False
        self._opacity.setOpacity(1.0)
        self.completed.emit()
