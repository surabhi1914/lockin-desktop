"""Session aggregate persistence without transaction ownership."""

import sqlite3
from collections.abc import Mapping

from app.diagnostics import database_path
from app.models.persisted_session import FINAL_SESSION_STATUSES, PersistedSession


class SessionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @property
    def database_path(self) -> str:
        return str(database_path(self._connection))

    def allocate_sequence(self, device_id: str) -> int:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(session_sequence), 0) + 1 FROM sessions WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        return int(row[0])

    def insert(self, values: Mapping[str, object]) -> None:
        columns = tuple(values)
        placeholders = ", ".join("?" for _ in columns)
        self._connection.execute(
            f"INSERT INTO sessions ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values[column] for column in columns),
        )

    def update(self, session_id: str, values: Mapping[str, object]) -> None:
        if not values:
            return
        assignments = ", ".join(f"{column} = ?" for column in values)
        cursor = self._connection.execute(
            f"UPDATE sessions SET {assignments} WHERE session_id = ?",
            (*values.values(), session_id),
        )
        if cursor.rowcount != 1:
            raise LookupError(f"session not found: {session_id}")

    def get(self, session_id: str) -> PersistedSession | None:
        row = self._connection.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return None if row is None else PersistedSession.from_row(row)

    def latest_finalized(self, limit: int = 20) -> tuple[PersistedSession, ...]:
        placeholders = ", ".join("?" for _ in FINAL_SESSION_STATUSES)
        rows = self._connection.execute(
            f"""
            SELECT * FROM sessions
            WHERE status IN ({placeholders}) AND ended_at_utc IS NOT NULL
            ORDER BY started_at_utc DESC, session_id DESC LIMIT ?
            """,
            (*FINAL_SESSION_STATUSES, limit),
        ).fetchall()
        return tuple(PersistedSession.from_row(row) for row in rows)

    def all(self) -> tuple[PersistedSession, ...]:
        return tuple(
            PersistedSession.from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM sessions ORDER BY started_at_utc, session_id"
            )
        )
