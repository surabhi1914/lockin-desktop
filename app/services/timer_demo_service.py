"""Developer-only in-memory composition service for the Phase 2 timer demo."""

from PySide6.QtCore import QObject, Signal

from app.timer.clock import Clock
from app.timer.models import TimerConfig, TimerSnapshot
from app.timer.qt_timer_adapter import QtTimerAdapter
from app.timer.timer_engine import TimerEngine


class TimerDemoService(QObject):
    """Own a disposable engine/adapter pair; never read or write persistent data."""

    snapshot_changed = Signal(object)
    state_changed = Signal(object)
    planned_completed = Signal(object)
    stopped = Signal(object)
    event_emitted = Signal(object)

    def __init__(
        self,
        config: TimerConfig | None = None,
        *,
        clock: Clock | None = None,
        poll_interval_ms: int = 150,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._poll_interval_ms = poll_interval_ms
        self._clock = clock
        self._engine: TimerEngine
        self._adapter: QtTimerAdapter
        self._snapshot: TimerSnapshot
        self._create(config or TimerConfig(10))

    @property
    def engine(self) -> TimerEngine:
        return self._engine

    @property
    def adapter(self) -> QtTimerAdapter:
        return self._adapter

    @property
    def current_snapshot(self) -> TimerSnapshot:
        return self._snapshot

    def start(self) -> TimerSnapshot:
        self._engine.start()
        snapshot = self._poll()
        self._adapter.start_polling()
        return snapshot

    def pause(self) -> TimerSnapshot:
        self._engine.pause()
        return self._poll()

    def resume(self) -> TimerSnapshot:
        self._engine.resume()
        return self._poll()

    def stop(self) -> TimerSnapshot:
        self._engine.stop()
        snapshot = self._poll()
        self._adapter.stop_polling()
        return snapshot

    def start_overtime(self) -> TimerSnapshot:
        self._engine.start_overtime()
        self._adapter.start_polling()
        return self._poll()

    def reset(self, config: TimerConfig | None = None) -> TimerSnapshot:
        """Discard the current demo and create a fresh in-memory engine."""
        selected_config = config or self._engine.config
        self._adapter.dispose()
        self._adapter.deleteLater()
        self._create(selected_config)
        return self._snapshot

    def dispose(self) -> None:
        self._adapter.dispose()

    def _create(self, config: TimerConfig) -> None:
        self._engine = TimerEngine(config, self._clock)
        self._adapter = QtTimerAdapter(
            self._engine,
            poll_interval_ms=self._poll_interval_ms,
            parent=self,
        )
        self._adapter.snapshot_changed.connect(self._on_snapshot)
        self._adapter.state_changed.connect(self.state_changed.emit)
        self._adapter.planned_completed.connect(self.planned_completed.emit)
        self._adapter.stopped.connect(self.stopped.emit)
        self._adapter.event_emitted.connect(self.event_emitted.emit)
        snapshot = self._adapter.poll_once()
        if snapshot is None:
            raise RuntimeError("new timer adapter was unexpectedly disposed")
        self._snapshot = snapshot

    def _poll(self) -> TimerSnapshot:
        snapshot = self._adapter.poll_once()
        if snapshot is None:
            raise RuntimeError("timer demo adapter is disposed")
        self._snapshot = snapshot
        return snapshot

    def _on_snapshot(self, snapshot: object) -> None:
        if not isinstance(snapshot, TimerSnapshot):
            raise TypeError("adapter emitted an invalid timer snapshot")
        self._snapshot = snapshot
        self.snapshot_changed.emit(snapshot)
