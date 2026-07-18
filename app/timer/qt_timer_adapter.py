"""Thin Qt polling adapter for the GUI-independent timer engine."""

from PySide6.QtCore import QObject, QTimer, Signal

from app.timer.enums import TimerEventType, TimerState
from app.timer.events import TimerEvent
from app.timer.models import TimerSnapshot
from app.timer.timer_engine import TimerEngine


class QtTimerAdapter(QObject):
    """Poll an engine on the owning Qt thread without owning timing truth."""

    snapshot_changed = Signal(object)
    state_changed = Signal(object)
    planned_completed = Signal(object)
    stopped = Signal(object)
    event_emitted = Signal(object)

    def __init__(
        self,
        engine: TimerEngine,
        *,
        poll_interval_ms: int = 150,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if isinstance(poll_interval_ms, bool) or not isinstance(poll_interval_ms, int):
            raise TypeError("poll_interval_ms must be an integer")
        if poll_interval_ms <= 0:
            raise ValueError("poll_interval_ms must be greater than zero")
        self._engine = engine
        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval_ms)
        self._timer.timeout.connect(self.poll_once)
        self._last_version: int | None = None
        self._last_state: TimerState | None = None
        self._completion_signaled = False
        self._stopped_signaled = False
        self._disposed = False

    @property
    def engine(self) -> TimerEngine:
        return self._engine

    @property
    def poll_interval_ms(self) -> int:
        return self._timer.interval()

    @property
    def is_polling(self) -> bool:
        return self._timer.isActive()

    @property
    def is_disposed(self) -> bool:
        return self._disposed

    def start_polling(self) -> None:
        if not self._disposed:
            self._timer.start()

    def stop_polling(self) -> None:
        self._timer.stop()

    def poll_once(self) -> TimerSnapshot | None:
        """Refresh once, emitting only newly observable snapshots and events."""
        if self._disposed:
            return None
        snapshot = self._engine.snapshot()
        if snapshot.version != self._last_version:
            self._last_version = snapshot.version
            self.snapshot_changed.emit(snapshot)
        if snapshot.state is not self._last_state:
            self._last_state = snapshot.state
            self.state_changed.emit(snapshot.state)
        for event in self._engine.drain_events():
            self._emit_event(event, snapshot)
        if snapshot.completion_emitted and not self._completion_signaled:
            self._completion_signaled = True
            self.planned_completed.emit(snapshot)
        if snapshot.state is TimerState.STOPPED and not self._stopped_signaled:
            self._stopped_signaled = True
            self.stopped.emit(snapshot)
        return snapshot

    def dispose(self) -> None:
        """Stop and disconnect polling without altering engine state."""
        if self._disposed:
            return
        self._timer.stop()
        self._timer.timeout.disconnect(self.poll_once)
        self._disposed = True

    def _emit_event(self, event: TimerEvent, snapshot: TimerSnapshot) -> None:
        self.event_emitted.emit(event)
        if event.event_type is TimerEventType.PLANNED_COMPLETED and not self._completion_signaled:
            self._completion_signaled = True
            self.planned_completed.emit(snapshot)
        if event.event_type is TimerEventType.TIMER_STOPPED and not self._stopped_signaled:
            self._stopped_signaled = True
            self.stopped.emit(snapshot)
