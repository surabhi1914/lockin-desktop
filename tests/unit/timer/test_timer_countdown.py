from decimal import Decimal

from app.timer import ManualClock, TimerConfig, TimerEngine, TimerState


def test_initial_snapshot_and_start_capabilities() -> None:
    engine = TimerEngine(TimerConfig(10), ManualClock())
    initial = engine.snapshot()
    assert initial.state is TimerState.IDLE
    assert initial.remaining_planned_seconds == 10
    assert initial.total_focus_ns == initial.total_pause_ns == initial.wall_elapsed_ns == 0
    assert not initial.can_pause and not initial.can_stop
    started = engine.start()
    assert started.can_pause and started.can_stop
    assert started.continuous_block_count == 1


def test_subsecond_elapsed_floor_and_remaining_ceiling() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(2), clock)
    engine.start()
    clock.advance_seconds(Decimal("0.25"))
    snapshot = engine.refresh()
    assert snapshot.planned_focus_seconds == 0
    assert snapshot.planned_focus_ns == 250_000_000
    assert snapshot.remaining_planned_seconds == 2
    clock.advance_seconds(Decimal("0.75"))
    assert engine.refresh().remaining_planned_seconds == 1


def test_irregular_polling_and_no_double_count() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(20), clock)
    engine.start()
    for seconds in (1, 4, 2, 7):
        clock.advance_seconds(seconds)
        engine.refresh()
    first = engine.snapshot()
    second = engine.snapshot()
    assert first.planned_focus_seconds == 14
    assert second.planned_focus_ns == first.planned_focus_ns
    assert second.version == first.version


def test_long_poll_overshoot_caps_planned_and_never_becomes_overtime() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(60), clock)
    engine.start()
    clock.advance_seconds(75)
    snapshot = engine.refresh()
    assert snapshot.state is TimerState.COMPLETED
    assert snapshot.planned_focus_seconds == snapshot.total_focus_seconds == 60
    assert snapshot.overtime_ns == snapshot.remaining_planned_ns == 0
    assert snapshot.wall_elapsed_seconds == 75


def test_decimal_steps_have_no_float_drift() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(1), clock)
    engine.start()
    for _ in range(10):
        clock.advance_seconds(Decimal("0.1"))
        engine.refresh()
    snapshot = engine.snapshot()
    assert snapshot.state is TimerState.COMPLETED
    assert snapshot.planned_focus_ns == 1_000_000_000
