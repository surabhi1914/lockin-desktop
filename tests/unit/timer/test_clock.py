from decimal import Decimal

import pytest

from app.timer.clock import ManualClock, MonotonicClock
from app.timer.errors import ClockRegressionError


def test_manual_clock_advances_exact_nanoseconds_and_decimal_seconds() -> None:
    clock = ManualClock(12)
    assert clock.advance_ns(8) == 20
    assert clock.advance_seconds(Decimal("0.000000001")) == 21
    assert clock.advance_seconds(2) == 2_000_000_021


@pytest.mark.parametrize("value", [True, 1.5, "1"])
def test_manual_clock_rejects_non_integer_nanoseconds(value: object) -> None:
    with pytest.raises(TypeError):
        ManualClock().advance_ns(value)  # type: ignore[arg-type]


def test_manual_clock_rejects_backward_movement() -> None:
    clock = ManualClock(10)
    with pytest.raises(ClockRegressionError):
        clock.set_ns(9)
    with pytest.raises(ClockRegressionError):
        clock.advance_ns(-1)


def test_manual_clock_rejects_sub_nanosecond_or_non_finite_seconds() -> None:
    with pytest.raises(ValueError):
        ManualClock().advance_seconds(Decimal("0.0000000001"))
    with pytest.raises(ValueError):
        ManualClock().advance_seconds(Decimal("Infinity"))


def test_production_clock_returns_integer() -> None:
    assert isinstance(MonotonicClock().now_ns(), int)
