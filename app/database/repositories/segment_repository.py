"""Focus and pause segment persistence without transaction ownership."""

import sqlite3
from collections.abc import Mapping

from app.models.persisted_segment import PersistedSegment


class SegmentRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def next_sequence(self, session_id: str) -> int:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(segment_sequence), 0) + 1 FROM segments WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row[0])

    def insert(self, values: Mapping[str, object]) -> None:
        columns = tuple(values)
        placeholders = ", ".join("?" for _ in columns)
        self._connection.execute(
            f"INSERT INTO segments ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values[column] for column in columns),
        )

    def open_for_session(self, session_id: str) -> PersistedSegment | None:
        row = self._connection.execute(
            "SELECT * FROM segments WHERE session_id = ? AND ended_at_utc IS NULL",
            (session_id,),
        ).fetchone()
        return None if row is None else PersistedSegment.from_row(row)

    def close(self, segment_id: str, values: Mapping[str, object]) -> None:
        assignments = ", ".join(f"{column} = ?" for column in values)
        cursor = self._connection.execute(
            f"UPDATE segments SET {assignments} WHERE segment_id = ? AND ended_at_utc IS NULL",
            (*values.values(), segment_id),
        )
        if cursor.rowcount != 1:
            raise LookupError(f"open segment not found: {segment_id}")

    def update_open(self, segment_id: str, values: Mapping[str, object]) -> None:
        assignments = ", ".join(f"{column} = ?" for column in values)
        cursor = self._connection.execute(
            f"UPDATE segments SET {assignments} WHERE segment_id = ? AND ended_at_utc IS NULL",
            (*values.values(), segment_id),
        )
        if cursor.rowcount != 1:
            raise LookupError(f"open segment not found: {segment_id}")

    def finalized_seconds(self, session_id: str, segment_type: str, phase: str) -> int:
        row = self._connection.execute(
            """
            SELECT COALESCE(SUM(duration_seconds), 0) FROM segments
            WHERE session_id = ? AND segment_type = ? AND focus_phase = ?
              AND ended_at_utc IS NOT NULL
            """,
            (session_id, segment_type, phase),
        ).fetchone()
        return int(row[0])

    def list_for_session(self, session_id: str) -> tuple[PersistedSegment, ...]:
        return tuple(
            PersistedSegment.from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM segments WHERE session_id = ? ORDER BY segment_sequence",
                (session_id,),
            )
        )
