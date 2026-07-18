import pytest

from app.timer import ManualClock, TimerConfig, TimerEngine, TimerState
from app.timer.errors import InvalidTimerTransitionError


def test_allowed_running_pause_resume_and_stop_transitions() -> None:
    engine = TimerEngine(TimerConfig(20), ManualClock())
    assert engine.start().state is TimerState.RUNNING
    assert engine.pause().state is TimerState.PAUSED
    assert engine.resume().state is TimerState.RUNNING
    assert engine.stop().state is TimerState.STOPPED


def test_pause_remembers_overtime_return_state() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(1), clock)
    engine.start()
    clock.advance_seconds(1)
    engine.refresh()
    engine.start_overtime()
    assert engine.pause().state is TimerState.PAUSED
    assert engine.resume().state is TimerState.OVERTIME


def test_invalid_operations_are_typed_and_include_state() -> None:
    engine = TimerEngine(TimerConfig(5), ManualClock())
    for operation in (engine.pause, engine.resume, engine.stop, engine.start_overtime):
        with pytest.raises(InvalidTimerTransitionError, match="idle"):
            operation()
    engine.start()
    with pytest.raises(InvalidTimerTransitionError, match="running"):
        engine.start()
    with pytest.raises(InvalidTimerTransitionError, match="running"):
        engine.resume()
    engine.pause()
    with pytest.raises(InvalidTimerTransitionError, match="paused"):
        engine.pause()


def test_stopped_timer_cannot_restart() -> None:
    engine = TimerEngine(TimerConfig(5), ManualClock())
    engine.start()
    engine.stop()
    with pytest.raises(InvalidTimerTransitionError, match="stopped"):
        engine.start()


def test_test_visible_invariant_validator_accepts_each_state() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(2), clock)
    engine.validate_invariants()
    engine.start()
    engine.validate_invariants()
    engine.pause()
    engine.validate_invariants()
    engine.resume()
    clock.advance_seconds(2)
    engine.refresh()
    engine.validate_invariants()
    engine.stop()
    engine.validate_invariants()
