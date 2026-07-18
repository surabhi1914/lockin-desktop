from decimal import Decimal

import pytest

from app.timer import ManualClock, TimerConfig, TimerEngine, TimerEventType
from app.timer.continuous_blocks import (
    calculate_continuous_blocks,
    summarize_block_durations,
)
from app.timer.enums import FocusPhase
from app.timer.models import FocusInterval, PauseInterval


@pytest.mark.parametrize("pause_seconds, expected", [(9, 1), (10, 1), (11, 2)])
def test_pause_grace_classifies_continuity_exactly(pause_seconds: int, expected: int) -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(30), clock)
    engine.start()
    clock.advance_seconds(2)
    engine.pause()
    clock.advance_seconds(pause_seconds)
    engine.resume()
    clock.advance_seconds(2)
    snapshot = engine.refresh()
    assert snapshot.continuous_block_count == expected
    assert snapshot.short_pause_count == (pause_seconds <= 10)
    assert snapshot.long_pause_count == (pause_seconds > 10)


def test_mixed_pauses_count_and_emit_only_long_breaks() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(30, pause_grace_seconds=3), clock)
    engine.start()
    engine.drain_events()
    for gap in (1, 4, 2, 5):
        clock.advance_seconds(1)
        engine.pause()
        clock.advance_seconds(gap)
        engine.resume()
    snapshot = engine.snapshot()
    continuity_events = [
        event
        for event in engine.drain_events()
        if event.event_type is TimerEventType.CONTINUITY_BROKEN
    ]
    assert snapshot.pause_count == 4
    assert snapshot.short_pause_count == snapshot.long_pause_count == 2
    assert snapshot.continuous_block_count == 3
    assert len(continuity_events) == 2


def test_direct_planned_to_overtime_is_one_block_with_both_phases() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(1), clock)
    engine.start()
    clock.advance_seconds(1)
    engine.refresh()
    engine.start_overtime()
    clock.advance_seconds(2)
    block = engine.refresh().continuous_blocks[0]
    assert block.includes_planned and block.includes_overtime
    assert block.duration_seconds == 3


def test_pure_calculator_odd_even_median_and_average_floor() -> None:
    intervals = (
        FocusInterval(0, 1, FocusPhase.PLANNED),
        FocusInterval(20, 24, FocusPhase.PLANNED),
        FocusInterval(40, 48, FocusPhase.OVERTIME),
    )
    blocks = calculate_continuous_blocks(intervals, (), grace_ns=0)
    assert summarize_block_durations(blocks) == (8, 4, 4, 8)
    even = calculate_continuous_blocks(intervals[:2], (), grace_ns=0)
    assert summarize_block_durations(even) == (4, 2, 2, 4)


def test_pure_calculator_counts_short_pauses_but_not_completion_gaps() -> None:
    intervals = (
        FocusInterval(0, 1_000_000_000, FocusPhase.PLANNED),
        FocusInterval(2_000_000_000, 3_000_000_000, FocusPhase.PLANNED),
        FocusInterval(4_000_000_000, 5_000_000_000, FocusPhase.OVERTIME),
    )
    pauses = (PauseInterval(1_000_000_000, 2_000_000_000),)
    block = calculate_continuous_blocks(intervals, pauses, 1_000_000_000)[0]
    assert block.short_pause_count == 1
    assert block.duration_seconds == 3


def test_exact_nanoseconds_not_rounded_for_grace() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(5, pause_grace_seconds=10), clock)
    engine.start()
    clock.advance_seconds(1)
    engine.pause()
    clock.advance_seconds(Decimal("10.000000001"))
    engine.resume()
    assert engine.snapshot().long_pause_count == 1
