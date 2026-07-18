"""Typed timer domain errors."""


class TimerError(Exception):
    """Base class for timer domain failures."""


class InvalidTimerConfigurationError(TimerError, ValueError):
    """Raised when a timer configuration violates domain limits."""


class InvalidTimerTransitionError(TimerError):
    """Raised when an operation is invalid for the current timer state."""


class ClockRegressionError(TimerError):
    """Raised when a clock attempts to move backward."""
