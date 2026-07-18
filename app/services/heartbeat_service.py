"""Five-second version-aware runtime heartbeat scheduler."""

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from app.services.session_persistence_service import SessionPersistenceService
from app.timer.models import TimerSnapshot


class HeartbeatService(QObject):
    repeated_failure = Signal(str)

    def __init__(
        self,
        persistence: SessionPersistenceService,
        snapshot_provider: Callable[[], TimerSnapshot],
        *,
        interval_ms: int = 5000,
        failure_threshold: int = 3,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._persistence = persistence
        self._snapshot_provider = snapshot_provider
        self._failure_threshold = failure_threshold
        self._failures = 0
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.tick)

    @property
    def active(self) -> bool:
        return self._timer.isActive()

    def start(self) -> None:
        self._failures = 0
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._failures = 0

    def tick(self) -> bool:
        try:
            changed = self._persistence.heartbeat(self._snapshot_provider())
        except RuntimeError as exc:
            self._failures += 1
            if self._failures >= self._failure_threshold:
                self.repeated_failure.emit(str(exc))
            return False
        self._failures = 0
        return changed
