"""Parameterized, read-only canonical statistics aggregation."""

import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date, timedelta
from statistics import median

from app.analytics.models import (
    AnalyticsFilters,
    CategoryMetric,
    DailyMetric,
    DeviceMetric,
    StatisticsResult,
)
from app.core.time_utils import parse_utc, split_at_local_midnights, validate_date

DEFAULT_STATUSES = (
    "completed",
    "completed_with_overtime",
    "stopped_early",
    "recovered",
)


class AnalyticsService:
    def __init__(self, connection: sqlite3.Connection, *, current_device_id: str = "") -> None:
        self._connection = connection
        self._current_device = current_device_id
        self._cache: dict[tuple[int, AnalyticsFilters], StatisticsResult] = {}

    def calculate(self, filters: AnalyticsFilters) -> StatisticsResult:
        start = validate_date(filters.from_date)
        end = validate_date(filters.to_date)
        if end < start:
            raise ValueError("statistics end date cannot precede start date")
        if filters.minimum_focus_seconds < 0:
            raise ValueError("minimum focus duration cannot be negative")
        key = (self._revision(), filters)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sessions = self._session_rows(filters, start, end)
        by_id = {str(row["session_id"]): row for row in sessions}
        segment_rows = self._related_rows("segments", by_id)
        distraction_rows = self._related_rows("distractions", by_id)
        result = self._aggregate(filters, start, end, sessions, segment_rows, distraction_rows)
        self._cache = {key: result}
        return result

    def invalidate(self) -> None:
        self._cache.clear()

    def _session_rows(self, filters: AnalyticsFilters, start: date, end: date) -> list[sqlite3.Row]:
        statuses: tuple[str, ...] = (
            tuple(filters.statuses) if filters.statuses else DEFAULT_STATUSES
        )
        if not filters.include_recovered:
            statuses = tuple(status for status in statuses if status != "recovered")
        if not statuses:
            return []
        clauses = [
            f"s.status IN ({','.join('?' for _ in statuses)})",
            "s.ended_at_utc IS NOT NULL",
            "s.local_date_started BETWEEN ? AND ?",
            "s.actual_focus_seconds >= ?",
        ]
        values: list[object] = [
            *statuses,
            (start - timedelta(days=7)).isoformat(),
            end.isoformat(),
            filters.minimum_focus_seconds,
        ]
        for column, selected in (
            ("s.category_id", filters.category_ids),
            ("s.device_id", filters.device_ids),
            ("s.entry_source", filters.entry_sources),
        ):
            if selected:
                clauses.append(f"{column} IN ({','.join('?' for _ in selected)})")
                values.extend(selected)
        return self._connection.execute(
            f"""
            SELECT s.*, d.device_label FROM sessions s
            JOIN devices d ON d.device_id=s.device_id
            WHERE {" AND ".join(clauses)}
            ORDER BY s.started_at_utc, s.session_id
            """,
            values,
        ).fetchall()

    def _related_rows(self, table: str, sessions: dict[str, sqlite3.Row]) -> list[sqlite3.Row]:
        if not sessions:
            return []
        identifiers = tuple(sessions)
        placeholders = ",".join("?" for _ in identifiers)
        order = "started_at_utc, segment_id" if table == "segments" else "marked_at_utc"
        return self._connection.execute(
            f"SELECT * FROM {table} WHERE session_id IN ({placeholders}) ORDER BY {order}",
            identifiers,
        ).fetchall()

    def _aggregate(
        self,
        filters: AnalyticsFilters,
        start: date,
        end: date,
        sessions: list[sqlite3.Row],
        segments: list[sqlite3.Row],
        distractions: list[sqlite3.Row],
    ) -> StatisticsResult:
        daily_focus: dict[date, int] = defaultdict(int)
        daily_pause: dict[date, int] = defaultdict(int)
        daily_sessions: dict[date, set[str]] = defaultdict(set)
        daily_distractions: dict[date, int] = defaultdict(int)
        blocks: dict[tuple[str, str], int] = defaultdict(int)
        daily_blocks: dict[tuple[date, str, str], int] = defaultdict(int)
        category_focus: dict[str, int] = defaultdict(int)
        category_overtime: dict[str, int] = defaultdict(int)
        category_sessions: dict[str, set[str]] = defaultdict(set)
        category_blocks: dict[tuple[str, str, str], int] = defaultdict(int)
        device_focus: dict[str, int] = defaultdict(int)
        device_sessions: dict[str, set[str]] = defaultdict(set)
        pause_count = short_pauses = long_pauses = sleep_pauses = 0
        sessions_by_id = {str(row["session_id"]): row for row in sessions}
        for row in segments:
            session = sessions_by_id.get(str(row["session_id"]))
            if session is None or row["ended_at_utc"] is None:
                continue
            parts = split_at_local_midnights(
                parse_utc(row["started_at_utc"]),
                parse_utc(row["ended_at_utc"]),
                row["timezone_name"],
            )
            durations = self._allocate(
                int(row["duration_seconds"]), [part.duration_seconds for part in parts]
            )
            in_range = False
            for part, duration in zip(parts, durations, strict=True):
                day = date.fromisoformat(part.local_date)
                if not start <= day <= end:
                    continue
                in_range = True
                session_id = str(row["session_id"])
                if bool(row["counts_as_focus"]):
                    if not filters.include_overtime and row["focus_phase"] == "overtime":
                        continue
                    daily_focus[day] += duration
                    daily_sessions[day].add(session_id)
                    category_id = str(session["category_id"])
                    device_id = str(session["device_id"])
                    category_focus[category_id] += duration
                    category_sessions[category_id].add(session_id)
                    device_focus[device_id] += duration
                    device_sessions[device_id].add(session_id)
                    group = str(row["continuity_group_id"] or row["segment_id"])
                    blocks[(session_id, group)] += duration
                    daily_blocks[(day, session_id, group)] += duration
                    category_blocks[(category_id, session_id, group)] += duration
                    if row["focus_phase"] == "overtime":
                        category_overtime[category_id] += duration
                elif row["segment_type"] == "pause":
                    daily_pause[day] += duration
            if in_range and row["segment_type"] == "pause":
                pause_count += 1
                classification = str(row["pause_classification"])
                short_pauses += classification == "short_grace_pause"
                sleep_pauses += classification == "system_sleep"
                long_pauses += classification in {"continuity_break", "system_sleep"}
        selected_sessions = [
            row for row in sessions if start <= date.fromisoformat(row["local_date_started"]) <= end
        ]
        session_ids = {str(row["session_id"]) for row in sessions}
        marked_sessions: set[str] = set()
        for row in distractions:
            day = date.fromisoformat(row["local_date"])
            session_id = str(row["session_id"])
            if start <= day <= end and session_id in session_ids:
                daily_distractions[day] += 1
                marked_sessions.add(session_id)
        goals = self._goals(start, end)
        daily_rows: list[DailyMetric] = []
        cursor = start
        while cursor <= end:
            longest = max(
                (value for (day, _session, _group), value in daily_blocks.items() if day == cursor),
                default=0,
            )
            daily_rows.append(
                DailyMetric(
                    cursor.isoformat(),
                    daily_focus.get(cursor, 0),
                    goals.get(cursor, 0),
                    len(daily_sessions.get(cursor, set())),
                    longest,
                    daily_pause.get(cursor, 0),
                    daily_distractions.get(cursor, 0),
                )
            )
            cursor += timedelta(days=1)
        focus_values = [row.focus_seconds for row in daily_rows if row.focus_seconds > 0]
        block_values = list(blocks.values())
        total_focus = sum(row.focus_seconds for row in daily_rows)
        total_pause = sum(row.pause_seconds for row in daily_rows)
        status_counts = Counter(str(row["status"]) for row in selected_sessions)
        completed = status_counts["completed"] + status_counts["completed_with_overtime"]
        planned = sum(int(row["planned_focus_seconds"]) for row in selected_sessions)
        planned_completed = sum(
            int(row["planned_focus_completed_seconds"]) for row in selected_sessions
        )
        overtime = (
            sum(int(row["overtime_seconds"]) for row in selected_sessions)
            if filters.include_overtime
            else 0
        )
        actual = planned_completed + overtime
        categories = self._category_metrics(
            sessions,
            category_focus,
            category_sessions,
            category_blocks,
            category_overtime,
        )
        devices = self._device_metrics(sessions, device_focus, device_sessions)
        distraction_count = sum(row.distraction_count for row in daily_rows)
        return StatisticsResult(
            filters,
            tuple(daily_rows),
            total_focus,
            self._mean(focus_values),
            self._median(focus_values),
            len(focus_values),
            sum(
                row.goal_seconds > 0 and row.focus_seconds >= row.goal_seconds for row in daily_rows
            ),
            self._best((row.local_date, row.focus_seconds) for row in daily_rows),
            self._best_period(daily_rows, "week"),
            self._best_period(daily_rows, "month"),
            len(selected_sessions),
            tuple(sorted(status_counts.items())),
            None if not selected_sessions else completed / len(selected_sessions),
            planned,
            planned_completed,
            None if planned == 0 else planned_completed / planned,
            sum(int(row["stopped_early_seconds"]) for row in selected_sessions),
            overtime,
            None if planned == 0 else actual / planned,
            len(block_values),
            max(block_values, default=0),
            self._mean(block_values),
            self._median(block_values),
            self._buckets(block_values),
            total_pause,
            pause_count,
            short_pauses,
            long_pauses,
            sleep_pauses,
            0 if pause_count == 0 else total_pause // pause_count,
            None if total_focus == 0 else total_pause / total_focus,
            distraction_count,
            None if total_focus == 0 else distraction_count / (total_focus / 3600),
            len(marked_sessions),
            None if not marked_sessions else distraction_count / len(marked_sessions),
            categories,
            devices,
        )

    def _category_metrics(
        self,
        sessions: list[sqlite3.Row],
        focus: dict[str, int],
        session_sets: dict[str, set[str]],
        blocks: dict[tuple[str, str, str], int],
        overtime: dict[str, int],
    ) -> tuple[CategoryMetric, ...]:
        names = {str(row["category_id"]): str(row["category_name_snapshot"]) for row in sessions}
        return tuple(
            CategoryMetric(
                category_id,
                names.get(category_id, "Unknown"),
                seconds,
                len(session_sets[category_id]),
                self._mean(
                    [
                        value
                        for (key, _session, _group), value in blocks.items()
                        if key == category_id
                    ]
                ),
                overtime[category_id],
            )
            for category_id, seconds in sorted(
                focus.items(), key=lambda item: (-item[1], names.get(item[0], ""))
            )
        )

    def _device_metrics(
        self,
        sessions: list[sqlite3.Row],
        focus: dict[str, int],
        session_sets: dict[str, set[str]],
    ) -> tuple[DeviceMetric, ...]:
        labels = {str(row["device_id"]): str(row["device_label"]) for row in sessions}
        return tuple(
            DeviceMetric(
                device_id,
                labels.get(device_id, "Unknown device"),
                seconds,
                len(session_sets[device_id]),
                device_id == self._current_device,
            )
            for device_id, seconds in sorted(focus.items(), key=lambda item: -item[1])
        )

    def _goals(self, start: date, end: date) -> dict[date, int]:
        rows = self._connection.execute(
            """
            SELECT * FROM daily_goals WHERE effective_from_date <= ?
              AND (effective_to_date IS NULL OR effective_to_date >= ?)
            ORDER BY effective_from_date
            """,
            (end.isoformat(), start.isoformat()),
        ).fetchall()
        result: dict[date, int] = {}
        cursor = start
        while cursor <= end:
            for row in rows:
                if row["effective_from_date"] <= cursor.isoformat() and (
                    row["effective_to_date"] is None
                    or row["effective_to_date"] >= cursor.isoformat()
                ):
                    result[cursor] = int(row["goal_seconds"])
                    break
            cursor += timedelta(days=1)
        return result

    def _revision(self) -> int:
        row = self._connection.execute(
            "SELECT value FROM app_metadata WHERE key='analytics_revision'"
        ).fetchone()
        return 0 if row is None else int(row[0])

    @staticmethod
    def _allocate(total: int, weights: list[int]) -> tuple[int, ...]:
        if not weights:
            return ()
        weight_total = sum(weights)
        if len(weights) == 1 or weight_total <= 0:
            return (total,)
        values = [total * weight // weight_total for weight in weights[:-1]]
        values.append(total - sum(values))
        return tuple(values)

    @staticmethod
    def _mean(values: list[int]) -> int:
        return 0 if not values else sum(values) // len(values)

    @staticmethod
    def _median(values: list[int]) -> int:
        return 0 if not values else int(median(values))

    @staticmethod
    def _best(values: Iterable[tuple[str, int]]) -> tuple[str, int] | None:
        rows = list(values)
        if not rows or max(item[1] for item in rows) == 0:
            return None
        return max(rows, key=lambda item: (item[1], item[0]))

    @staticmethod
    def _best_period(rows: list[DailyMetric], period: str) -> tuple[str, int] | None:
        totals: dict[str, int] = defaultdict(int)
        for row in rows:
            day = date.fromisoformat(row.local_date)
            if period == "week":
                key = (day - timedelta(days=day.weekday())).isoformat()
            else:
                key = day.strftime("%Y-%m")
            totals[key] += row.focus_seconds
        return AnalyticsService._best(totals.items())

    @staticmethod
    def _buckets(values: list[int]) -> tuple[tuple[str, int], ...]:
        counts = Counter(
            "under_15m"
            if value < 900
            else "15_24m"
            if value < 1500
            else "25_49m"
            if value < 3000
            else "50_89m"
            if value < 5400
            else "90m_plus"
            for value in values
        )
        return tuple(
            (label, counts[label])
            for label in ("under_15m", "15_24m", "25_49m", "50_89m", "90m_plus")
        )
