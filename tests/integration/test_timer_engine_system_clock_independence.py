import inspect
import time

import pytest

from app.timer import ManualClock, TimerConfig, TimerEngine
from app.timer import timer_engine as timer_engine_module


def test_manual_clock_engine_ignores_wall_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_wall_clock() -> float:
        raise AssertionError("wall clock must not be used")

    monkeypatch.setattr(time, "time", fail_wall_clock)
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(2), clock)
    engine.start()
    clock.advance_seconds(1)
    assert engine.refresh().planned_focus_seconds == 1


def test_engine_source_has_no_sleep_thread_or_wall_clock_timing() -> None:
    source = inspect.getsource(timer_engine_module)
    assert "datetime.now" not in source
    assert "time.time" not in source
    assert "sleep(" not in source
    assert "threading" not in source
    assert "remaining -= 1" not in source
