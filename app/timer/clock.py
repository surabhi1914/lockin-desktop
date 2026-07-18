"""Clock abstractions used by the timer engine."""

from decimal import Decimal
from time import monotonic_ns
from typing import Protocol

from app.timer.errors import ClockRegressionError

NANOSECONDS_PER_SECOND = 1_000_000_000


class Clock(Protocol):
    """Minimal monotonic clock contract."""

    def now_ns(self) -> int:
        """Return the current monotonic time in integer nanoseconds."""
        ...


class MonotonicClock:
    """Production clock backed by the operating system monotonic clock."""

    def now_ns(self) -> int:
        return monotonic_ns()


class ManualClock:
    """Exact, non-sleeping, test-controlled monotonic clock."""

    def __init__(self, initial_ns: int = 0) -> None:
        if isinstance(initial_ns, bool) or not isinstance(initial_ns, int):
            raise TypeError("initial_ns must be an integer")
        if initial_ns < 0:
            raise ClockRegressionError("manual clock cannot start below zero")
        self._now_ns = initial_ns

    def now_ns(self) -> int:
        return self._now_ns

    def set_ns(self, value: int) -> None:
        """Set an exact time without permitting backward movement."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("manual clock value must be an integer")
        if value < self._now_ns:
            raise ClockRegressionError(
                f"manual clock cannot move backward from {self._now_ns}ns to {value}ns"
            )
        self._now_ns = value

    def advance_ns(self, nanoseconds: int) -> int:
        """Advance by an exact non-negative integer number of nanoseconds."""
        if isinstance(nanoseconds, bool) or not isinstance(nanoseconds, int):
            raise TypeError("nanoseconds must be an integer")
        if nanoseconds < 0:
            raise ClockRegressionError("manual clock cannot advance by a negative duration")
        self._now_ns += nanoseconds
        return self._now_ns

    def advance_seconds(self, seconds: int | Decimal) -> int:
        """Advance by seconds exactly, accepting integers or finite Decimals."""
        if isinstance(seconds, bool) or not isinstance(seconds, (int, Decimal)):
            raise TypeError("seconds must be an integer or Decimal")
        decimal_seconds = Decimal(seconds)
        if not decimal_seconds.is_finite():
            raise ValueError("seconds must be finite")
        nanoseconds = decimal_seconds * NANOSECONDS_PER_SECOND
        integral_nanoseconds = nanoseconds.to_integral_value()
        if nanoseconds != integral_nanoseconds:
            raise ValueError("seconds must resolve to a whole number of nanoseconds")
        return self.advance_ns(int(integral_nanoseconds))
