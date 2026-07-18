"""Testable power-event source and sleep state projection."""

from enum import StrEnum

from PySide6.QtCore import QObject, Signal


class PowerEvent(StrEnum):
    SUSPEND = "suspend"
    RESUME_AUTOMATIC = "resume_automatic"
    RESUME_USER = "resume_user"


class PowerEventSource(QObject):
    event_received = Signal(object)

    def emit_event(self, event: PowerEvent) -> None:
        self.event_received.emit(event)


class SleepDetector(QObject):
    suspended = Signal()
    resumed = Signal()

    def __init__(self, source: PowerEventSource, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._suspended = False
        source.event_received.connect(self._event)

    @property
    def is_suspended(self) -> bool:
        return self._suspended

    def _event(self, value: object) -> None:
        if value is PowerEvent.SUSPEND:
            if not self._suspended:
                self._suspended = True
                self.suspended.emit()
        elif value in {PowerEvent.RESUME_AUTOMATIC, PowerEvent.RESUME_USER} and self._suspended:
            self._suspended = False
            self.resumed.emit()
