from app.timer import ManualClock, TimerConfig, TimerEngine, TimerState


def test_version_changes_only_for_observable_changes() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(5), clock)
    initial = engine.snapshot()
    assert engine.snapshot().version == initial.version == 0
    started = engine.start()
    assert started.version == 1
    assert engine.snapshot().version == 1
    clock.advance_ns(1)
    assert engine.snapshot().version == 2


def test_snapshot_capabilities_follow_state() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(1), clock)
    assert not engine.snapshot().can_pause
    running = engine.start()
    assert running.can_pause and not running.can_resume and not running.can_start_overtime
    paused = engine.pause()
    assert paused.can_resume and not paused.can_pause
    engine.resume()
    clock.advance_seconds(1)
    completed = engine.refresh()
    assert completed.state is TimerState.COMPLETED
    assert completed.can_start_overtime
    stopped = engine.stop()
    assert not any(
        (stopped.can_pause, stopped.can_resume, stopped.can_stop, stopped.can_start_overtime)
    )


def test_wall_elapsed_excludes_prestart_and_poststop_time() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(20), clock)
    clock.advance_seconds(100)
    assert engine.snapshot().wall_elapsed_ns == 0
    engine.start()
    clock.advance_seconds(7)
    stopped = engine.stop()
    clock.advance_seconds(50)
    assert stopped.wall_elapsed_seconds == 7
    assert engine.snapshot().wall_elapsed_seconds == 7


def test_current_block_active_only_during_focus() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(10), clock)
    engine.start()
    assert engine.snapshot().current_block_active
    engine.pause()
    assert not engine.snapshot().current_block_active
    engine.resume()
    assert engine.snapshot().current_block_active
    engine.stop()
    assert not engine.snapshot().current_block_active
