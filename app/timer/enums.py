"""Timer domain enumerations."""

from enum import StrEnum


class TimerState(StrEnum):
    """Lifecycle state of one in-memory timer."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    OVERTIME = "overtime"
    STOPPED = "stopped"


class TimerEventType(StrEnum):
    """Events emitted by timer transitions."""

    TIMER_STARTED = "timer_started"
    TIMER_PAUSED = "timer_paused"
    TIMER_RESUMED = "timer_resumed"
    PLANNED_COMPLETED = "planned_completed"
    OVERTIME_STARTED = "overtime_started"
    TIMER_STOPPED = "timer_stopped"
    CONTINUITY_BROKEN = "continuity_broken"


class FocusPhase(StrEnum):
    """The type of focus represented by an interval."""

    PLANNED = "planned"
    OVERTIME = "overtime"
