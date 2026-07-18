"""Read-only startup detection for unresolved heartbeat state."""

from dataclasses import dataclass

from app.database.repositories.runtime_state_repository import RuntimeStateRepository
from app.database.repositories.session_repository import SessionRepository


@dataclass(frozen=True, slots=True)
class UnfinishedSession:
    session_id: str
    category_name: str
    started_at_local: str
    timer_state: str
    last_heartbeat_at_utc: str | None


class UnfinishedDetectorService:
    def __init__(
        self,
        runtime_states: RuntimeStateRepository,
        sessions: SessionRepository,
    ) -> None:
        self._runtime_states = runtime_states
        self._sessions = sessions

    def detect(self) -> tuple[UnfinishedSession, ...]:
        unresolved: list[UnfinishedSession] = []
        for runtime in self._runtime_states.all():
            session = self._sessions.get(runtime.session_id)
            if session is None:
                continue
            unresolved.append(
                UnfinishedSession(
                    session.session_id,
                    session.category_name_snapshot,
                    session.started_at_local,
                    runtime.timer_state,
                    runtime.last_heartbeat_at_utc,
                )
            )
        return tuple(unresolved)
