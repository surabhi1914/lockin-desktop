from decimal import Decimal

from app.timer import ManualClock, TimerConfig, TimerEngine, TimerEventType, TimerState


def test_scenario_countdown_pause_resume_and_early_stop() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(20), clock)
    engine.start()
    clock.advance_seconds(3)
    engine.pause()
    clock.advance_seconds(6)
    paused = engine.refresh()
    assert paused.planned_focus_seconds == 3
    assert paused.total_pause_seconds == 6
    engine.resume()
    clock.advance_seconds(2)
    stopped = engine.stop()
    assert stopped.state is TimerState.STOPPED
    assert stopped.planned_focus_seconds == 5
    assert stopped.wall_elapsed_seconds == 11


def test_scenario_overshoot_wait_and_explicit_overtime() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(10), clock)
    engine.start()
    clock.advance_seconds(15)
    completed = engine.refresh()
    assert completed.state is TimerState.COMPLETED
    assert completed.total_focus_seconds == 10
    clock.advance_seconds(2)
    engine.start_overtime()
    clock.advance_seconds(3)
    overtime = engine.refresh()
    assert overtime.planned_focus_seconds == 10
    assert overtime.overtime_seconds == 3
    assert overtime.total_focus_seconds == 13
    assert overtime.wall_elapsed_seconds == 20


def test_scenario_ten_second_continuity_rule() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(60), clock)
    engine.start()
    clock.advance_seconds(5)
    engine.pause()
    clock.advance_seconds(10)
    engine.resume()
    clock.advance_seconds(5)
    engine.pause()
    clock.advance_seconds(Decimal("10.000000001"))
    engine.resume()
    clock.advance_seconds(5)
    snapshot = engine.refresh()
    breaks = [
        event
        for event in engine.drain_events()
        if event.event_type is TimerEventType.CONTINUITY_BROKEN
    ]
    assert snapshot.continuous_block_count == 2
    assert snapshot.short_pause_count == 1
    assert snapshot.long_pause_count == 1
    assert len(breaks) == 1


def test_scenario_repeated_refreshes_preserve_accounting_invariants() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(3), clock)
    engine.start()
    for nanoseconds in (1, 999_999_999, 500_000_000, 1_500_000_000):
        clock.advance_ns(nanoseconds)
        snapshot = engine.refresh()
        assert snapshot.total_focus_ns == snapshot.planned_focus_ns + snapshot.overtime_ns
        assert snapshot.remaining_planned_ns >= 0
        assert snapshot.pause_count == snapshot.short_pause_count + snapshot.long_pause_count
    assert engine.snapshot().state is TimerState.COMPLETED
