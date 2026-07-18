"""Timezone-aware wall clocks used only for persisted timestamps."""

from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.models.errors import InvalidWallClockError


class WallClock(Protocol):
    def now_utc(self) -> datetime:
        """Return a timezone-aware UTC instant."""
        ...


def require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidWallClockError("wall clock must return a timezone-aware timestamp")
    if value.utcoffset() != timedelta(0):
        raise InvalidWallClockError("wall clock must return UTC")
    return value.astimezone(UTC)


class SystemWallClock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)


class ManualWallClock:
    def __init__(self, initial: datetime) -> None:
        self._now = require_utc(initial)

    def now_utc(self) -> datetime:
        return self._now

    def set(self, value: datetime) -> None:
        candidate = require_utc(value)
        if candidate < self._now:
            raise InvalidWallClockError("manual wall clock cannot move backward")
        self._now = candidate

    def advance(self, *, seconds: int) -> None:
        if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 0:
            raise InvalidWallClockError("wall-clock advance must be a non-negative integer")
        self._now += timedelta(seconds=seconds)
