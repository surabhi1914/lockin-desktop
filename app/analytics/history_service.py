"""Advanced read-only session history with bounded parameterized pagination."""

import sqlite3
from dataclasses import dataclass
from typing import ClassVar

from app.database.repositories.distraction_repository import DistractionRepository
from app.database.repositories.recovery_event_repository import RecoveryEventRepository
from app.database.repositories.segment_repository import SegmentRepository
from app.database.repositories.session_repository import SessionRepository
from app.diagnostics import database_path, trace_manual_session
from app.models.persisted_distraction import PersistedDistraction
from app.models.persisted_segment import PersistedSegment
from app.models.persisted_session import PersistedSession
from app.models.recovery_event import RecoveryEvent
from app.models.sync_ledger_entry import SyncLedgerEntry


@dataclass(frozen=True, slots=True)
class HistoryFilters:
    search: str = ""
    from_date: str | None = None
    to_date: str | None = None
    category_ids: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    device_ids: tuple[str, ...] = ()
    entry_sources: tuple[str, ...] = ()
    overtime_only: bool = False
    distraction_only: bool = False
    minimum_focus_seconds: int | None = None
    maximum_focus_seconds: int | None = None
    sort_by: str = "started_desc"
    page: int = 1
    page_size: int = 50


@dataclass(frozen=True, slots=True)
class HistoryRow:
    session_id: str
    started_at_local: str
    category_name: str
    device_label: str
    planned_seconds: int
    focus_seconds: int
    overtime_seconds: int
    pause_seconds: int
    distraction_count: int
    status: str
    entry_source: str


@dataclass(frozen=True, slots=True)
class HistoryPageResult:
    rows: tuple[HistoryRow, ...]
    total_count: int
    page: int
    page_size: int


@dataclass(frozen=True, slots=True)
class SessionDetail:
    session: PersistedSession
    segments: tuple[PersistedSegment, ...]
    distractions: tuple[PersistedDistraction, ...]
    recovery_events: tuple[RecoveryEvent, ...]
    sync_entries: tuple[SyncLedgerEntry, ...]


class HistoryService:
    SORTS: ClassVar[dict[str, str]] = {
        "started_desc": "s.started_at_utc DESC, s.session_id DESC",
        "started_asc": "s.started_at_utc ASC, s.session_id ASC",
        "focus_desc": "s.actual_focus_seconds DESC, s.started_at_utc DESC",
        "focus_asc": "s.actual_focus_seconds ASC, s.started_at_utc DESC",
        "category": "s.category_name_snapshot COLLATE NOCASE, s.started_at_utc DESC",
    }

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._sessions = SessionRepository(connection)
        self._segments = SegmentRepository(connection)
        self._distractions = DistractionRepository(connection)
        self._recovery = RecoveryEventRepository(connection)

    @property
    def database_path(self) -> str:
        return str(database_path(self._connection))

    def search(self, filters: HistoryFilters) -> HistoryPageResult:
        if filters.page < 1 or not 1 <= filters.page_size <= 200:
            raise ValueError("history page and page size are outside supported limits")
        if filters.sort_by not in self.SORTS:
            raise ValueError("unsupported history sort")
        clauses = ["s.ended_at_utc IS NOT NULL"]
        if not filters.statuses:
            clauses.append("s.status != 'discarded'")
        values: list[object] = []
        if filters.search.strip():
            clauses.append(
                "(s.category_name_snapshot LIKE ? ESCAPE '\\' OR s.session_id LIKE ? ESCAPE '\\')"
            )
            escaped = self._like(filters.search.strip())
            values.extend((f"%{escaped}%", f"%{escaped}%"))
        for column, selected in (
            ("s.category_id", filters.category_ids),
            ("s.status", filters.statuses),
            ("s.device_id", filters.device_ids),
            ("s.entry_source", filters.entry_sources),
        ):
            if selected:
                clauses.append(f"{column} IN ({','.join('?' for _ in selected)})")
                values.extend(selected)
        for operator, boundary in ((">=", filters.from_date), ("<=", filters.to_date)):
            if boundary is not None:
                clauses.append(f"s.local_date_started {operator} ?")
                values.append(boundary)
        if filters.overtime_only:
            clauses.append("s.overtime_seconds > 0")
        if filters.distraction_only:
            clauses.append("s.distraction_count > 0")
        if filters.minimum_focus_seconds is not None:
            clauses.append("s.actual_focus_seconds >= ?")
            values.append(filters.minimum_focus_seconds)
        if filters.maximum_focus_seconds is not None:
            clauses.append("s.actual_focus_seconds <= ?")
            values.append(filters.maximum_focus_seconds)
        where = " AND ".join(clauses)
        source = "sessions s LEFT JOIN devices d ON d.device_id=s.device_id"
        total = int(
            self._connection.execute(
                f"SELECT COUNT(*) FROM {source} WHERE {where}", values
            ).fetchone()[0]
        )
        rows = self._connection.execute(
            f"""
            SELECT s.*, COALESCE(d.device_label, 'Unknown device') AS device_label
            FROM {source}
            WHERE {where} ORDER BY {self.SORTS[filters.sort_by]}
            LIMIT ? OFFSET ?
            """,
            (*values, filters.page_size, (filters.page - 1) * filters.page_size),
        ).fetchall()
        result = HistoryPageResult(
            tuple(
                HistoryRow(
                    row["session_id"],
                    row["started_at_local"],
                    row["category_name_snapshot"],
                    row["device_label"],
                    row["planned_focus_seconds"],
                    row["actual_focus_seconds"],
                    row["overtime_seconds"],
                    row["total_pause_seconds"],
                    row["distraction_count"],
                    row["status"],
                    row["entry_source"],
                )
                for row in rows
            ),
            total,
            filters.page,
            filters.page_size,
        )
        trace_manual_session(
            "history-query",
            connection=self._connection,
            total_count=result.total_count,
            returned_count=len(result.rows),
            page=result.page,
            page_size=result.page_size,
            entry_sources=list(filters.entry_sources),
            statuses=list(filters.statuses),
            from_date=filters.from_date,
            to_date=filters.to_date,
            result_ids=[row.session_id for row in result.rows],
        )
        return result

    def detail(self, session_id: str) -> SessionDetail:
        session = self._sessions.get(session_id)
        if session is None or session.ended_at_utc is None:
            raise LookupError(f"finalized session not found: {session_id}")
        segments = self._segments.list_for_session(session_id)
        distractions = self._distractions.list_for_session(session_id)
        recovery = self._recovery.list_for_session(session_id)
        identifiers = [session_id]
        identifiers.extend(segment.segment_id for segment in segments)
        identifiers.extend(item.distraction_id for item in distractions)
        placeholders = ",".join("?" for _ in identifiers)
        ledger = tuple(
            SyncLedgerEntry.from_row(row)
            for row in self._connection.execute(
                f"""
                SELECT * FROM sync_ledger WHERE record_id IN ({placeholders})
                ORDER BY record_type, record_id
                """,
                identifiers,
            )
        )
        return SessionDetail(session, segments, distractions, recovery, ledger)

    def filter_options(self) -> dict[str, tuple[tuple[str, str], ...]]:
        categories = tuple(
            (str(row[0]), str(row[1]))
            for row in self._connection.execute(
                "SELECT category_id, category_name FROM categories "
                "ORDER BY category_name COLLATE NOCASE"
            )
        )
        devices = tuple(
            (str(row[0]), str(row[1]))
            for row in self._connection.execute(
                "SELECT device_id, device_label FROM devices ORDER BY device_label COLLATE NOCASE"
            )
        )
        statuses = tuple(
            (str(row[0]), str(row[0]))
            for row in self._connection.execute(
                "SELECT DISTINCT status FROM sessions "
                "WHERE ended_at_utc IS NOT NULL ORDER BY status"
            )
        )
        return {
            "categories": categories,
            "devices": devices,
            "statuses": statuses,
            "sources": (
                ("timer", "Timer"),
                ("manual", "Manual"),
                ("recovery", "Recovery"),
                ("imported", "Imported"),
            ),
        }

    @staticmethod
    def _like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
