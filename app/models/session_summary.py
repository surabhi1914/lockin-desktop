"""Final database-backed local session summary."""

from dataclasses import dataclass

from app.models.persisted_session import PersistedSession


@dataclass(frozen=True, slots=True)
class SessionSummary:
    session_id: str
    category_name: str
    started_at_local: str
    ended_at_local: str
    planned_duration_seconds: int
    planned_focus_seconds: int
    overtime_seconds: int
    total_focus_seconds: int
    total_pause_seconds: int
    pause_count: int
    distraction_count: int
    continuous_block_count: int
    longest_continuous_seconds: int
    average_continuous_seconds: int
    status: str
    saved_locally: bool = True
    portable_synced: bool | None = None
    sync_message: str = "Saved locally; portable sync pending"

    @classmethod
    def from_session(cls, session: PersistedSession) -> "SessionSummary":
        if session.ended_at_local is None:
            raise ValueError("cannot summarize an unfinished session")
        return cls(
            session_id=session.session_id,
            category_name=session.category_name_snapshot,
            started_at_local=session.started_at_local,
            ended_at_local=session.ended_at_local,
            planned_duration_seconds=session.planned_focus_seconds,
            planned_focus_seconds=session.planned_focus_completed_seconds,
            overtime_seconds=session.overtime_seconds,
            total_focus_seconds=session.actual_focus_seconds,
            total_pause_seconds=session.total_pause_seconds,
            pause_count=session.pause_count,
            distraction_count=session.distraction_count,
            continuous_block_count=session.continuous_block_count,
            longest_continuous_seconds=session.longest_continuous_seconds,
            average_continuous_seconds=session.average_continuous_seconds,
            status=session.status,
        )
