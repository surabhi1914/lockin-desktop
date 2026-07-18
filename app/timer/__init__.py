"""GUI-independent timer domain for LockIn."""

from app.timer.clock import Clock, ManualClock, MonotonicClock
from app.timer.enums import FocusPhase, TimerEventType, TimerState
from app.timer.errors import (
    ClockRegressionError,
    InvalidTimerConfigurationError,
    InvalidTimerTransitionError,
    TimerError,
)
from app.timer.events import TimerEvent
from app.timer.models import ContinuousBlock, TimerConfig, TimerSnapshot
from app.timer.timer_engine import TimerEngine

__all__ = [
    "Clock",
    "ClockRegressionError",
    "ContinuousBlock",
    "FocusPhase",
    "InvalidTimerConfigurationError",
    "InvalidTimerTransitionError",
    "ManualClock",
    "MonotonicClock",
    "TimerConfig",
    "TimerEngine",
    "TimerError",
    "TimerEvent",
    "TimerEventType",
    "TimerSnapshot",
    "TimerState",
]
