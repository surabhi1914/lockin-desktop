from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.core.wall_clock import ManualWallClock, SystemWallClock, require_utc
from app.models.errors import InvalidWallClockError


def test_system_and_manual_wall_clocks_require_aware_utc() -> None:
    assert SystemWallClock().now_utc().tzinfo is UTC
    initial = datetime(2026, 7, 16, tzinfo=UTC)
    clock = ManualWallClock(initial)
    clock.advance(seconds=5)
    assert clock.now_utc() == initial + timedelta(seconds=5)
    clock.set(initial + timedelta(seconds=8))
    assert clock.now_utc() == initial + timedelta(seconds=8)


@pytest.mark.parametrize(
    "value",
    [datetime(2026, 7, 16), datetime(2026, 7, 16, tzinfo=timezone(timedelta(hours=-4)))],
)
def test_wall_clock_rejects_naive_and_non_utc(value: datetime) -> None:
    with pytest.raises(InvalidWallClockError):
        require_utc(value)


def test_manual_wall_clock_rejects_regression_and_invalid_advance() -> None:
    clock = ManualWallClock(datetime(2026, 7, 16, tzinfo=UTC))
    with pytest.raises(InvalidWallClockError, match="backward"):
        clock.set(datetime(2026, 7, 15, tzinfo=UTC))
    for invalid in (-1, True, 1.5):
        with pytest.raises(InvalidWallClockError):
            clock.advance(seconds=invalid)  # type: ignore[arg-type]
