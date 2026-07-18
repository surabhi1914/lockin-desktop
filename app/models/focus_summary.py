"""Immutable, in-memory-only Phase 4 focus summary."""

from dataclasses import dataclass
from enum import StrEnum

from app.models.session_summary import SessionSummary
from app.timer.models import TimerSnapshot


class FocusSummaryStatus(StrEnum):
    COMPLETED = "Completed"
    COMPLETED_WITH_OVERTIME = "Completed with overtime"
    STOPPED_EARLY = "Stopped early"


@dataclass(frozen=True, slots=True)
class FocusSummary:
    category_name: str
    planned_duration_seconds: int
    planned_focus_seconds: int
    overtime_seconds: int
    total_focus_seconds: int
    total_pause_seconds: int
    pause_count: int
    longest_continuous_seconds: int
    average_continuous_seconds: int
    distraction_count: int
    status: FocusSummaryStatus
    session_id: str | None = None
    started_at_local: str | None = None
    ended_at_local: str | None = None
    continuous_block_count: int = 0
    saved_locally: bool = False
    portable_synced: bool | None = None
    sync_message: str = "Saved locally; portable sync pending"

    @classmethod
    def from_snapshot(
        cls,
        category_name: str,
        snapshot: TimerSnapshot,
        *,
        distraction_count: int = 0,
    ) -> "FocusSummary":
        if snapshot.overtime_seconds > 0:
            status = FocusSummaryStatus.COMPLETED_WITH_OVERTIME
        elif snapshot.planned_complete:
            status = FocusSummaryStatus.COMPLETED
        else:
            status = FocusSummaryStatus.STOPPED_EARLY
        return cls(
            category_name=category_name,
            planned_duration_seconds=snapshot.planned_duration_seconds,
            planned_focus_seconds=snapshot.planned_focus_seconds,
            overtime_seconds=snapshot.overtime_seconds,
            total_focus_seconds=snapshot.total_focus_seconds,
            total_pause_seconds=snapshot.total_pause_seconds,
            pause_count=snapshot.pause_count,
            longest_continuous_seconds=snapshot.longest_continuous_seconds,
            average_continuous_seconds=snapshot.average_continuous_seconds,
            distraction_count=distraction_count,
            status=status,
        )

    @classmethod
    def from_persisted(cls, summary: SessionSummary) -> "FocusSummary":
        statuses = {
            "completed": FocusSummaryStatus.COMPLETED,
            "completed_with_overtime": FocusSummaryStatus.COMPLETED_WITH_OVERTIME,
            "stopped_early": FocusSummaryStatus.STOPPED_EARLY,
        }
        return cls(
            category_name=summary.category_name,
            planned_duration_seconds=summary.planned_duration_seconds,
            planned_focus_seconds=summary.planned_focus_seconds,
            overtime_seconds=summary.overtime_seconds,
            total_focus_seconds=summary.total_focus_seconds,
            total_pause_seconds=summary.total_pause_seconds,
            pause_count=summary.pause_count,
            longest_continuous_seconds=summary.longest_continuous_seconds,
            average_continuous_seconds=summary.average_continuous_seconds,
            distraction_count=summary.distraction_count,
            status=statuses[summary.status],
            session_id=summary.session_id,
            started_at_local=summary.started_at_local,
            ended_at_local=summary.ended_at_local,
            continuous_block_count=summary.continuous_block_count,
            saved_locally=True,
            portable_synced=summary.portable_synced,
            sync_message=summary.sync_message,
        )
