"""Immutable timer domain events."""

from dataclasses import dataclass

from app.timer.clock import NANOSECONDS_PER_SECOND
from app.timer.enums import TimerEventType, TimerState

EventDetailValue = str | int | bool | None
EventDetails = tuple[tuple[str, EventDetailValue], ...]


@dataclass(frozen=True, slots=True)
class TimerEvent:
    """A single ordered timer transition event."""

    event_type: TimerEventType
    sequence: int
    offset_ns: int
    state: TimerState
    planned_focus_ns: int
    overtime_ns: int
    pause_ns: int
    total_focus_ns: int
    details: EventDetails = ()

    @property
    def offset_seconds(self) -> int:
        return self.offset_ns // NANOSECONDS_PER_SECOND

    @property
    def planned_focus_seconds(self) -> int:
        return self.planned_focus_ns // NANOSECONDS_PER_SECOND

    @property
    def overtime_seconds(self) -> int:
        return self.overtime_ns // NANOSECONDS_PER_SECOND

    @property
    def pause_seconds(self) -> int:
        return self.pause_ns // NANOSECONDS_PER_SECOND

    def details_dict(self) -> dict[str, EventDetailValue]:
        """Return a plain serializable details mapping for logs or adapters."""
        return dict(self.details)
