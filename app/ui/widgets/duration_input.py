"""Validated hours/minutes focus-duration input."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from app.models.errors import InvalidFocusSessionDraftError
from app.ui.widgets.validation_message import ValidationMessage

SECONDS_PER_MINUTE = 60
MINIMUM_DURATION_SECONDS = 60
MAXIMUM_DURATION_SECONDS = 7 * 24 * 60 * 60


class DurationInput(QWidget):
    """Integer-only duration input with a one-minute minimum."""

    value_changed = Signal(int)
    validity_changed = Signal(bool)

    def __init__(self, hours: int = 0, minutes: int = 50, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("durationInput")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(5)
        row = QHBoxLayout()
        form = QFormLayout()
        self.hours_input = QSpinBox()
        self.hours_input.setObjectName("durationHoursInput")
        self.hours_input.setAccessibleName("Focus duration hours")
        self.hours_input.setRange(0, 167)
        self.hours_input.setSuffix(" h")
        self.minutes_input = QSpinBox()
        self.minutes_input.setObjectName("durationMinutesInput")
        self.minutes_input.setAccessibleName("Focus duration minutes")
        self.minutes_input.setRange(0, 59)
        self.minutes_input.setSuffix(" min")
        form.addRow("Hours", self.hours_input)
        form.addRow("Minutes", self.minutes_input)
        row.addLayout(form)
        row.addStretch(1)
        outer.addLayout(row)
        self.summary_label = QLabel()
        self.summary_label.setObjectName("durationSummary")
        self.summary_label.setProperty("muted", True)
        outer.addWidget(self.summary_label)
        self.validation = ValidationMessage()
        outer.addWidget(self.validation)
        self._last_valid = False
        self.hours_input.valueChanged.connect(self._update)
        self.minutes_input.valueChanged.connect(self._update)
        self.set_duration(hours, minutes)

    @property
    def hours(self) -> int:
        return self.hours_input.value()

    @property
    def minutes(self) -> int:
        return self.minutes_input.value()

    @property
    def is_valid(self) -> bool:
        seconds = self._raw_seconds()
        return MINIMUM_DURATION_SECONDS <= seconds <= MAXIMUM_DURATION_SECONDS

    def duration_seconds(self) -> int:
        seconds = self._raw_seconds()
        if seconds < MINIMUM_DURATION_SECONDS:
            raise InvalidFocusSessionDraftError("Duration must be at least one minute.")
        if seconds > MAXIMUM_DURATION_SECONDS:
            raise InvalidFocusSessionDraftError("Duration cannot exceed seven days.")
        return seconds

    def set_duration(self, hours: int, minutes: int) -> None:
        self.hours_input.setValue(hours)
        self.minutes_input.setValue(minutes)
        self._update()

    def _raw_seconds(self) -> int:
        return (self.hours * 60 + self.minutes) * SECONDS_PER_MINUTE

    def _update(self) -> None:
        total_minutes = self.hours * 60 + self.minutes
        if total_minutes == 0:
            self.summary_label.setText("Choose at least one minute.")
            self.validation.set_error("Duration must be at least one minute.")
        else:
            parts: list[str] = []
            if self.hours:
                parts.append(f"{self.hours} hour{'s' if self.hours != 1 else ''}")
            if self.minutes:
                parts.append(f"{self.minutes} minute{'s' if self.minutes != 1 else ''}")
            self.summary_label.setText("Planned focus: " + " ".join(parts))
            self.validation.clear_error()
        valid = self.is_valid
        self.value_changed.emit(self._raw_seconds())
        if valid != self._last_valid:
            self._last_valid = valid
            self.validity_changed.emit(valid)
