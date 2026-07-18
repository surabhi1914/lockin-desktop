from app.timer import ManualClock, TimerConfig, TimerEngine, TimerEventType, TimerState


def test_exact_completion_emits_once_and_stays_at_zero() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(10), clock)
    engine.start()
    engine.drain_events()
    clock.advance_seconds(10)
    first = engine.refresh()
    clock.advance_seconds(10)
    second = engine.refresh()
    events = engine.drain_events()
    assert first.state is second.state is TimerState.COMPLETED
    assert second.remaining_planned_seconds == 0
    assert [event.event_type for event in events] == [TimerEventType.PLANNED_COMPLETED]


def test_completion_wait_changes_wall_but_not_focus() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(2), clock)
    engine.start()
    clock.advance_seconds(2)
    engine.refresh()
    clock.advance_seconds(7)
    snapshot = engine.refresh()
    assert snapshot.wall_elapsed_seconds == 9
    assert snapshot.total_focus_seconds == 2


def test_stop_from_running_completed_and_overtime() -> None:
    running = TimerEngine(TimerConfig(5), ManualClock())
    running.start()
    assert running.stop().state is TimerState.STOPPED

    completed_clock = ManualClock()
    completed = TimerEngine(TimerConfig(1), completed_clock)
    completed.start()
    completed_clock.advance_seconds(1)
    completed.refresh()
    assert completed.stop().state is TimerState.STOPPED

    overtime_clock = ManualClock()
    overtime = TimerEngine(TimerConfig(1), overtime_clock)
    overtime.start()
    overtime_clock.advance_seconds(1)
    overtime.refresh()
    overtime.start_overtime()
    assert overtime.stop().state is TimerState.STOPPED


def test_stopped_snapshot_never_changes_after_clock_advances() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(10), clock)
    engine.start()
    clock.advance_seconds(3)
    stopped = engine.stop()
    clock.advance_seconds(100)
    assert engine.snapshot() is stopped


def test_event_draining_removes_events_but_snapshot_does_not() -> None:
    engine = TimerEngine(TimerConfig(5), ManualClock())
    engine.start()
    engine.snapshot()
    assert len(engine.drain_events()) == 1
    assert engine.drain_events() == ()
