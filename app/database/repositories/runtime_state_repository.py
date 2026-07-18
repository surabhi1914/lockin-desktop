"""Heartbeat runtime-state persistence without transaction ownership."""

import sqlite3
from collections.abc import Mapping

from app.models.runtime_session_state import RuntimeSessionState


class RuntimeStateRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def insert(self, values: Mapping[str, object]) -> None:
        columns = tuple(values)
        placeholders = ", ".join("?" for _ in columns)
        self._connection.execute(
            f"INSERT INTO runtime_session_state ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values[column] for column in columns),
        )

    def update_if_new_version(
        self, session_id: str, values: Mapping[str, object], version: int
    ) -> bool:
        assignments = ", ".join(f"{column} = ?" for column in values)
        cursor = self._connection.execute(
            f"""
            UPDATE runtime_session_state SET {assignments}
            WHERE session_id = ? AND timer_version < ?
            """,
            (*values.values(), session_id, version),
        )
        return cursor.rowcount == 1

    def get(self, session_id: str) -> RuntimeSessionState | None:
        row = self._connection.execute(
            "SELECT * FROM runtime_session_state WHERE session_id = ?", (session_id,)
        ).fetchone()
        return None if row is None else RuntimeSessionState.from_row(row)

    def all(self) -> tuple[RuntimeSessionState, ...]:
        return tuple(
            RuntimeSessionState.from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM runtime_session_state ORDER BY updated_at_utc"
            )
        )

    def delete(self, session_id: str) -> None:
        self._connection.execute(
            "DELETE FROM runtime_session_state WHERE session_id = ?", (session_id,)
        )
