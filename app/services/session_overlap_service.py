"""UI-independent overlap assessment for historical session intervals."""

import sqlite3
from datetime import datetime

from app.core.time_utils import format_utc
from app.models.manual_session import OverlapKind, SessionOverlap


class SessionOverlapService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def assess(
        self,
        *,
        started_at_utc: datetime,
        ended_at_utc: datetime,
        category_id: str,
    ) -> SessionOverlap:
        start = format_utc(started_at_utc)
        end = format_utc(ended_at_utc)
        unresolved = self._connection.execute(
            """
            SELECT DISTINCT s.session_id
            FROM sessions s
            LEFT JOIN runtime_session_state r ON r.session_id = s.session_id
            LEFT JOIN recovery_events e
              ON e.session_id = s.session_id AND e.finalized_at_utc IS NULL
            WHERE r.session_id IS NOT NULL OR e.recovery_event_id IS NOT NULL
               OR s.status IN ('running', 'paused')
            ORDER BY s.session_id
            """
        ).fetchall()
        if unresolved:
            return SessionOverlap(
                OverlapKind.UNRESOLVED, tuple(str(row["session_id"]) for row in unresolved)
            )
        rows = self._connection.execute(
            """
            SELECT session_id, category_id, started_at_utc, ended_at_utc
            FROM sessions
            WHERE status != 'discarded' AND ended_at_utc IS NOT NULL
              AND started_at_utc < ? AND ended_at_utc > ?
            ORDER BY started_at_utc, session_id
            """,
            (end, start),
        ).fetchall()
        if not rows:
            return SessionOverlap(OverlapKind.NONE)
        identifiers = tuple(str(row["session_id"]) for row in rows)
        if any(
            row["started_at_utc"] == start
            and row["ended_at_utc"] == end
            and row["category_id"] == category_id
            for row in rows
        ):
            return SessionOverlap(OverlapKind.DUPLICATE, identifiers)
        full = any(
            row["category_id"] != category_id
            and (
                (row["started_at_utc"] <= start and row["ended_at_utc"] >= end)
                or (start <= row["started_at_utc"] and end >= row["ended_at_utc"])
            )
            for row in rows
        )
        return SessionOverlap(OverlapKind.FULL if full else OverlapKind.PARTIAL, identifiers)
