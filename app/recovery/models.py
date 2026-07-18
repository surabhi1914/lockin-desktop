"""Typed recovery analysis and result models."""

from dataclasses import dataclass
from enum import StrEnum


class RecoveryType(StrEnum):
    CRASH = "crash"
    MISSED_SUSPEND = "missed_suspend"
    SYSTEM_SLEEP = "system_sleep"
    RUNTIME_MISMATCH = "runtime_mismatch"
    COMPLETED_NOT_FINALIZED = "completed_not_finalized"
    OVERTIME_INTERRUPTED = "overtime_interrupted"
    PAUSED_INTERRUPTED = "paused_interrupted"


class RecoveryAction(StrEnum):
    SAVE_CONFIRMED = "save_confirmed"
    DISCARD = "discard"
    RESUME_AFTER_SLEEP = "resume_after_sleep"
    STOP_AFTER_SLEEP = "stop_after_sleep"
    AUTO_PAUSE = "auto_pause"


class SleepResumeDecision(StrEnum):
    RESUME = "resume"
    STOP_AND_SAVE = "stop_and_save"
    STAY_PAUSED = "stay_paused"


@dataclass(frozen=True, slots=True)
class RecoveryAnalysis:
    recovery_event_id: str
    session_id: str
    category_name: str
    planned_focus_seconds: int
    confirmed_planned_focus_seconds: int
    confirmed_overtime_seconds: int
    confirmed_pause_seconds: int
    confirmed_wall_clock_seconds: int
    last_heartbeat_at_utc: str | None
    confirmed_boundary_at_utc: str
    detected_at_utc: str
    unknown_gap_seconds: int
    original_timer_state: str
    open_segment_id: str | None
    open_segment_type: str | None
    recovery_type: RecoveryType
    can_resume_after_sleep: bool
    recommended_action: RecoveryAction
    warnings: tuple[str, ...]

    @property
    def confirmed_focus_seconds(self) -> int:
        return self.confirmed_planned_focus_seconds + self.confirmed_overtime_seconds


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    session_id: str
    action: RecoveryAction
    final_status: str
    confirmed_focus_seconds: int
    unknown_gap_seconds: int
    portable_synced: bool
    message: str
