import pytest

from app.timer import ManualClock, TimerConfig, TimerEngine, TimerState
from app.timer.errors import InvalidTimerTransitionError


def test_disabled_or_early_overtime_is_rejected() -> None:
    clock = ManualClock()
    disabled = TimerEngine(TimerConfig(1, overtime_enabled=False), clock)
    disabled.start()
    with pytest.raises(InvalidTimerTransitionError):
        disabled.start_overtime()
    clock.advance_seconds(1)
    disabled.refresh()
    with pytest.raises(InvalidTimerTransitionError, match="disabled"):
        disabled.start_overtime()


def test_explicit_overtime_counts_up_without_changing_planned_focus() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(2), clock)
    engine.start()
    clock.advance_seconds(5)
    engine.refresh()
    clock.advance_seconds(3)
    started = engine.start_overtime()
    assert started.overtime_ns == 0
    clock.advance_seconds(4)
    snapshot = engine.refresh()
    assert snapshot.state is TimerState.OVERTIME
    assert snapshot.planned_focus_seconds == 2
    assert snapshot.overtime_seconds == 4
    assert snapshot.total_focus_seconds == 6


def test_pause_resume_and_stop_in_overtime() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(1), clock)
    engine.start()
    clock.advance_seconds(1)
    engine.refresh()
    engine.start_overtime()
    clock.advance_seconds(2)
    engine.pause()
    clock.advance_seconds(3)
    paused = engine.refresh()
    assert paused.overtime_seconds == 2
    engine.resume()
    clock.advance_seconds(1)
    stopped = engine.stop()
    assert stopped.overtime_seconds == 3
    assert stopped.total_pause_seconds == 3


@pytest.mark.parametrize("gap, expected_blocks", [(10, 1), (11, 2)])
def test_completion_gap_uses_exact_grace(gap: int, expected_blocks: int) -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(1, pause_grace_seconds=10), clock)
    engine.start()
    clock.advance_seconds(1)
    engine.refresh()
    clock.advance_seconds(gap)
    engine.start_overtime()
    clock.advance_seconds(1)
    assert engine.refresh().continuous_block_count == expected_blocks
