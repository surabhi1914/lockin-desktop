"""Recovery audit persistence without transaction ownership."""

import sqlite3
from collections.abc import Mapping

from app.models.recovery_event import RecoveryEvent


class RecoveryEventRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def insert(self, values: Mapping[str, object]) -> None:
        columns = tuple(values)
        placeholders = ", ".join("?" for _ in columns)
        self._connection.execute(
            f"INSERT INTO recovery_events ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values[column] for column in columns),
        )

    def update(self, event_id: str, values: Mapping[str, object]) -> None:
        assignments = ", ".join(f"{column} = ?" for column in values)
        cursor = self._connection.execute(
            f"UPDATE recovery_events SET {assignments} WHERE recovery_event_id = ?",
            (*values.values(), event_id),
        )
        if cursor.rowcount != 1:
            raise LookupError(f"recovery event not found: {event_id}")

    def latest_for_session(self, session_id: str) -> RecoveryEvent | None:
        row = self._connection.execute(
            """
            SELECT * FROM recovery_events WHERE session_id = ?
            ORDER BY detected_at_utc DESC, recovery_event_id DESC LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        return None if row is None else RecoveryEvent.from_row(row)

    def list_for_session(self, session_id: str) -> tuple[RecoveryEvent, ...]:
        return tuple(
            RecoveryEvent.from_row(row)
            for row in self._connection.execute(
                """
                SELECT * FROM recovery_events WHERE session_id = ?
                ORDER BY detected_at_utc, recovery_event_id
                """,
                (session_id,),
            )
        )
