"""Immutable timer configuration, interval, block, and snapshot models."""

from dataclasses import dataclass

from app.timer.clock import NANOSECONDS_PER_SECOND
from app.timer.enums import FocusPhase, TimerState
from app.timer.errors import InvalidTimerConfigurationError

MAX_PLANNED_DURATION_SECONDS = 7 * 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class TimerConfig:
    """Validated configuration for one timer run."""

    planned_duration_seconds: int
    pause_grace_seconds: int = 10
    overtime_enabled: bool = True

    def __post_init__(self) -> None:
        duration = self.planned_duration_seconds
        grace = self.pause_grace_seconds
        if isinstance(duration, bool) or not isinstance(duration, int):
            raise InvalidTimerConfigurationError(
                "planned_duration_seconds must be an integer, not bool or float"
            )
        if duration <= 0:
            raise InvalidTimerConfigurationError("planned duration must be greater than zero")
        if duration > MAX_PLANNED_DURATION_SECONDS:
            raise InvalidTimerConfigurationError("planned duration cannot exceed seven days")
        if isinstance(grace, bool) or not isinstance(grace, int):
            raise InvalidTimerConfigurationError(
                "pause_grace_seconds must be a non-negative integer"
            )
        if grace < 0:
            raise InvalidTimerConfigurationError("pause grace cannot be negative")
        if not isinstance(self.overtime_enabled, bool):
            raise InvalidTimerConfigurationError("overtime_enabled must be a bool")

    @property
    def planned_duration_ns(self) -> int:
        return self.planned_duration_seconds * NANOSECONDS_PER_SECOND

    @property
    def pause_grace_ns(self) -> int:
        return self.pause_grace_seconds * NANOSECONDS_PER_SECOND


@dataclass(frozen=True, slots=True)
class FocusInterval:
    """One exact focus interval, expressed as offsets from first start."""

    start_offset_ns: int
    end_offset_ns: int
    phase: FocusPhase
    active: bool = False

    def __post_init__(self) -> None:
        if self.start_offset_ns < 0 or self.end_offset_ns < self.start_offset_ns:
            raise ValueError("focus interval cannot run backward")

    @property
    def duration_ns(self) -> int:
        return self.end_offset_ns - self.start_offset_ns


@dataclass(frozen=True, slots=True)
class PauseInterval:
    """One finalized pause, expressed as offsets from first start."""

    start_offset_ns: int
    end_offset_ns: int

    def __post_init__(self) -> None:
        if self.start_offset_ns < 0 or self.end_offset_ns < self.start_offset_ns:
            raise ValueError("pause interval cannot run backward")

    @property
    def duration_ns(self) -> int:
        return self.end_offset_ns - self.start_offset_ns


@dataclass(frozen=True, slots=True)
class ContinuousBlock:
    """Analytical focus block joined across gaps within the grace threshold."""

    index: int
    duration_ns: int
    duration_seconds: int
    start_offset_ns: int
    end_offset_ns: int | None
    includes_planned: bool
    includes_overtime: bool
    short_pause_count: int


@dataclass(frozen=True, slots=True)
class TimerSnapshot:
    """Immutable observable timer state.

    Elapsed displays use floor division. Remaining planned seconds use ceiling
    division. Exact nanosecond fields remain available for domain decisions.
    """

    state: TimerState
    planned_duration_seconds: int
    planned_duration_ns: int
    remaining_planned_seconds: int
    remaining_planned_ns: int
    planned_focus_seconds: int
    planned_focus_ns: int
    overtime_seconds: int
    overtime_ns: int
    total_focus_seconds: int
    total_focus_ns: int
    total_pause_seconds: int
    total_pause_ns: int
    wall_elapsed_seconds: int
    wall_elapsed_ns: int
    planned_complete: bool
    can_pause: bool
    can_resume: bool
    can_stop: bool
    can_start_overtime: bool
    pause_grace_seconds: int
    pause_count: int
    short_pause_count: int
    long_pause_count: int
    continuous_blocks: tuple[ContinuousBlock, ...]
    continuous_block_count: int
    longest_continuous_seconds: int
    longest_continuous_ns: int
    average_continuous_seconds: int
    average_continuous_ns: int
    median_continuous_seconds: int
    median_continuous_ns: int
    current_continuous_seconds: int
    current_continuous_ns: int
    current_block_active: bool
    completion_emitted: bool
    version: int

    @property
    def grace_seconds(self) -> int:
        """Compatibility-friendly short name for the configured pause grace."""
        return self.pause_grace_seconds
