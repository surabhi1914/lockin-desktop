from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from app.services.timer_demo_service import TimerDemoService
from app.timer import ManualClock, TimerConfig, TimerEngine, TimerEventType, TimerState
from app.timer.qt_timer_adapter import QtTimerAdapter


def test_adapter_emits_snapshots_only_on_version_change(qapp: QApplication) -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(5), clock)
    adapter = QtTimerAdapter(engine, poll_interval_ms=100)
    snapshots = QSignalSpy(adapter.snapshot_changed)
    states = QSignalSpy(adapter.state_changed)
    adapter.poll_once()
    adapter.poll_once()
    assert snapshots.count() == 1
    assert states.count() == 1
    engine.start()
    adapter.poll_once()
    adapter.poll_once()
    assert snapshots.count() == 2
    assert states.count() == 2
    adapter.dispose()


def test_adapter_completion_and_stop_signals_emit_once(qapp: QApplication) -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(1), clock)
    adapter = QtTimerAdapter(engine)
    completed = QSignalSpy(adapter.planned_completed)
    stopped = QSignalSpy(adapter.stopped)
    engine.start()
    clock.advance_seconds(1)
    adapter.poll_once()
    adapter.poll_once()
    engine.stop()
    adapter.poll_once()
    adapter.poll_once()
    assert completed.count() == 1
    assert stopped.count() == 1
    adapter.dispose()


def test_adapter_polling_lifecycle_does_not_change_engine(qapp: QApplication) -> None:
    engine = TimerEngine(TimerConfig(5), ManualClock())
    adapter = QtTimerAdapter(engine, poll_interval_ms=25)
    adapter.start_polling()
    assert adapter.is_polling
    assert engine.state is TimerState.IDLE
    adapter.stop_polling()
    assert not adapter.is_polling
    adapter.dispose()
    adapter.dispose()
    assert adapter.is_disposed
    assert adapter.poll_once() is None
    assert engine.state is TimerState.IDLE


def test_demo_service_controls_fresh_in_memory_engine(qapp: QApplication) -> None:
    clock = ManualClock()
    service = TimerDemoService(TimerConfig(2), clock=clock)
    original_engine = service.engine
    service.start()
    clock.advance_seconds(1)
    service.adapter.poll_once()
    assert service.current_snapshot.planned_focus_seconds == 1
    reset = service.reset(TimerConfig(3))
    assert service.engine is not original_engine
    assert reset.state is TimerState.IDLE
    assert reset.planned_duration_seconds == 3
    service.dispose()


def test_demo_service_forwards_events_and_state(qapp: QApplication) -> None:
    service = TimerDemoService(TimerConfig(1), clock=ManualClock())
    events = QSignalSpy(service.event_emitted)
    states = QSignalSpy(service.state_changed)
    service.start()
    QCoreApplication.processEvents()
    assert events.count() == 1
    event = events.at(0)[0]
    assert event.event_type is TimerEventType.TIMER_STARTED
    assert states.at(states.count() - 1)[0] is TimerState.RUNNING
    service.dispose()
