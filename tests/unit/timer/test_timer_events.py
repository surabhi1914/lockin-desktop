from app.timer import ManualClock, TimerConfig, TimerEngine, TimerEventType, TimerState


def test_transition_events_are_ordered_immutable_snapshots() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(2), clock)
    engine.start()
    clock.advance_seconds(1)
    engine.pause()
    clock.advance_seconds(1)
    engine.resume()
    clock.advance_seconds(1)
    engine.refresh()
    engine.start_overtime()
    engine.stop()
    events = engine.drain_events()
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert [event.event_type for event in events] == [
        TimerEventType.TIMER_STARTED,
        TimerEventType.TIMER_PAUSED,
        TimerEventType.TIMER_RESUMED,
        TimerEventType.PLANNED_COMPLETED,
        TimerEventType.OVERTIME_STARTED,
        TimerEventType.TIMER_STOPPED,
    ]
    assert events[-1].state is TimerState.STOPPED


def test_event_details_are_plain_serializable_values() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(10), clock)
    engine.start()
    engine.pause()
    clock.advance_seconds(1)
    engine.resume()
    resumed = engine.drain_events()[-1]
    assert resumed.details_dict() == {"pause_duration_ns": 1_000_000_000}


class RegressingClock:
    def __init__(self) -> None:
        self.value = 10

    def now_ns(self) -> int:
        return self.value


def test_engine_detects_clock_regression() -> None:
    from app.timer.errors import ClockRegressionError

    clock = RegressingClock()
    engine = TimerEngine(TimerConfig(1), clock)
    engine.start()
    clock.value = 9
    try:
        engine.snapshot()
    except ClockRegressionError:
        pass
    else:
        raise AssertionError("clock regression was not rejected")
