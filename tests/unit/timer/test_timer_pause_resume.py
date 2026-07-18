from decimal import Decimal

import pytest

from app.timer import ManualClock, TimerConfig, TimerEngine, TimerState
from app.timer.errors import InvalidTimerTransitionError


def test_pause_includes_focus_to_exact_boundary_and_freezes_it() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(20), clock)
    engine.start()
    clock.advance_seconds(Decimal("3.25"))
    paused = engine.pause()
    assert paused.planned_focus_ns == 3_250_000_000
    clock.advance_seconds(5)
    later = engine.refresh()
    assert later.planned_focus_ns == 3_250_000_000
    assert later.total_pause_seconds == 5


def test_resume_preserves_subsecond_remainder_and_classifies_pause() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(5), clock)
    engine.start()
    clock.advance_seconds(Decimal("1.2"))
    engine.pause()
    clock.advance_seconds(Decimal("2.5"))
    resumed = engine.resume()
    assert resumed.state is TimerState.RUNNING
    assert resumed.pause_count == resumed.short_pause_count == 1
    clock.advance_seconds(Decimal("0.8"))
    assert engine.refresh().planned_focus_seconds == 2


def test_multiple_pause_cycles_account_exactly() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(10, pause_grace_seconds=2), clock)
    engine.start()
    for pause_seconds in (1, 3, 2):
        clock.advance_seconds(1)
        engine.pause()
        clock.advance_seconds(pause_seconds)
        engine.resume()
    snapshot = engine.snapshot()
    assert snapshot.planned_focus_seconds == 3
    assert snapshot.total_pause_seconds == 6
    assert snapshot.pause_count == 3
    assert snapshot.short_pause_count == 2
    assert snapshot.long_pause_count == 1


def test_stop_while_paused_finalizes_pause() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(10), clock)
    engine.start()
    clock.advance_seconds(2)
    engine.pause()
    clock.advance_seconds(4)
    stopped = engine.stop()
    assert stopped.state is TimerState.STOPPED
    assert stopped.planned_focus_seconds == 2
    assert stopped.total_pause_seconds == 4
    assert stopped.pause_count == 1


def test_pause_at_completion_boundary_completes_then_rejects_pause() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(3), clock)
    engine.start()
    clock.advance_seconds(3)
    with pytest.raises(InvalidTimerTransitionError, match="completed"):
        engine.pause()
    assert engine.snapshot().state is TimerState.COMPLETED
