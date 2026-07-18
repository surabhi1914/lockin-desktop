"""Read-only access to final local session summaries and recent history."""

from app.database.repositories.session_repository import SessionRepository
from app.models.session_summary import SessionSummary


class SessionAggregateService:
    def __init__(self, sessions: SessionRepository) -> None:
        self._sessions = sessions

    def summary(self, session_id: str) -> SessionSummary:
        session = self._sessions.get(session_id)
        if session is None:
            raise LookupError(f"session not found: {session_id}")
        return SessionSummary.from_session(session)

    def latest(self, limit: int = 20) -> tuple[SessionSummary, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ValueError("recent-session limit must be between 1 and 20")
        return tuple(
            SessionSummary.from_session(item) for item in self._sessions.latest_finalized(limit)
        )
