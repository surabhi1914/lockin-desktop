"""UI-independent overlap assessment for historical session intervals."""

import sqlite3
from datetime import datetime

from app.core.time_utils import format_local, format_utc, get_timezone, parse_utc
from app.diagnostics import database_path, trace_manual_session
from app.models.manual_session import OverlapConflict, OverlapKind, SessionOverlap


class SessionOverlapService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @property
    def database_path(self) -> str:
        return str(database_path(self._connection))

    def assess(
        self,
        *,
        started_at_utc: datetime,
        ended_at_utc: datetime,
        category_id: str,
        exclude_session_id: str | None = None,
    ) -> SessionOverlap:
        start = format_utc(started_at_utc)
        end = format_utc(ended_at_utc)
        exclusion = "" if exclude_session_id is None else "AND s.session_id != ?"
        parameters: tuple[object, ...] = (
            (end, start) if exclude_session_id is None else (end, start, exclude_session_id)
        )
        unresolved = self._connection.execute(
            f"""
            SELECT s.session_id, s.entry_source, s.category_name_snapshot, s.status,
                   s.started_at_local, s.timezone_name,
                   COALESCE(
                       MAX(e.confirmed_boundary_at_utc),
                       r.last_heartbeat_at_utc,
                       r.updated_at_utc,
                       s.updated_at_utc,
                       s.started_at_utc
                   ) AS confirmed_end_utc
            FROM sessions s
            LEFT JOIN runtime_session_state r ON r.session_id = s.session_id
            LEFT JOIN recovery_events e
              ON e.session_id = s.session_id AND e.finalized_at_utc IS NULL
            WHERE s.status != 'discarded'
              AND (
                  r.session_id IS NOT NULL
                  OR e.recovery_event_id IS NOT NULL
                  OR s.status IN ('running', 'paused')
              )
              {exclusion}
            GROUP BY s.session_id
            HAVING s.started_at_utc < ? AND confirmed_end_utc > ?
            ORDER BY s.started_at_utc, s.session_id
            """,
            ((exclude_session_id, end, start) if exclude_session_id is not None else (end, start)),
        ).fetchall()
        if unresolved:
            conflicts = tuple(self._unresolved_conflict(row) for row in unresolved)
            result = SessionOverlap(
                OverlapKind.UNRESOLVED,
                tuple(conflict.session_id for conflict in conflicts),
                conflicts,
            )
            self._trace_result(start, end, result)
            return result
        rows = self._connection.execute(
            f"""
            SELECT s.session_id, s.category_id, s.category_name_snapshot,
                   s.entry_source, s.status, s.started_at_utc, s.ended_at_utc,
                   s.started_at_local, s.ended_at_local
            FROM sessions s
            WHERE s.status != 'discarded' AND s.ended_at_utc IS NOT NULL
              AND s.started_at_utc < ? AND s.ended_at_utc > ?
              {exclusion}
            ORDER BY s.started_at_utc, s.session_id
            """,
            parameters,
        ).fetchall()
        if not rows:
            result = SessionOverlap(OverlapKind.NONE)
            self._trace_result(start, end, result)
            return result
        identifiers = tuple(str(row["session_id"]) for row in rows)
        conflicts = tuple(self._finalized_conflict(row) for row in rows)
        if any(
            row["started_at_utc"] == start
            and row["ended_at_utc"] == end
            and row["category_id"] == category_id
            for row in rows
        ):
            result = SessionOverlap(OverlapKind.DUPLICATE, identifiers, conflicts)
            self._trace_result(start, end, result)
            return result
        full = any(
            row["category_id"] != category_id
            and (
                (row["started_at_utc"] <= start and row["ended_at_utc"] >= end)
                or (start <= row["started_at_utc"] and end >= row["ended_at_utc"])
            )
            for row in rows
        )
        result = SessionOverlap(
            OverlapKind.FULL if full else OverlapKind.PARTIAL,
            identifiers,
            conflicts,
        )
        self._trace_result(start, end, result)
        return result

    @staticmethod
    def _finalized_conflict(row: sqlite3.Row) -> OverlapConflict:
        return OverlapConflict(
            str(row["session_id"]),
            str(row["entry_source"]),
            str(row["category_name_snapshot"]),
            str(row["status"]),
            str(row["started_at_local"]),
            str(row["ended_at_local"]),
        )

    @staticmethod
    def _unresolved_conflict(row: sqlite3.Row) -> OverlapConflict:
        confirmed_end = parse_utc(str(row["confirmed_end_utc"])).astimezone(
            get_timezone(str(row["timezone_name"]))
        )
        return OverlapConflict(
            str(row["session_id"]),
            str(row["entry_source"]),
            str(row["category_name_snapshot"]),
            str(row["status"]),
            str(row["started_at_local"]),
            format_local(confirmed_end),
        )

    def _trace_result(self, start: str, end: str, overlap: SessionOverlap) -> None:
        trace_manual_session(
            "overlap-query",
            connection=self._connection,
            proposed_start_utc=start,
            proposed_end_utc=end,
            predicate="existing_start < proposed_end AND existing_end > proposed_start",
            kind=overlap.kind.value,
            conflict_count=len(overlap.session_ids),
            conflict_ids=list(overlap.session_ids),
        )
