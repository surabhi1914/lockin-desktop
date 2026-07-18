"""Distraction persistence without transaction ownership."""

import sqlite3
from collections.abc import Mapping

from app.models.persisted_distraction import PersistedDistraction


class DistractionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def insert_if_missing(self, values: Mapping[str, object]) -> bool:
        columns = tuple(values)
        placeholders = ", ".join("?" for _ in columns)
        cursor = self._connection.execute(
            f"INSERT OR IGNORE INTO distractions ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values[column] for column in columns),
        )
        return cursor.rowcount == 1

    def count(self, session_id: str) -> int:
        return int(
            self._connection.execute(
                "SELECT COUNT(*) FROM distractions WHERE session_id = ?", (session_id,)
            ).fetchone()[0]
        )

    def list_for_session(self, session_id: str) -> tuple[PersistedDistraction, ...]:
        return tuple(
            PersistedDistraction.from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM distractions WHERE session_id = ? ORDER BY marked_at_utc",
                (session_id,),
            )
        )
