"""Canonical local-date dashboard aggregation with revision-aware caching."""

import sqlite3
from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime, timedelta

from app.core.constants import DEFAULT_TIMEZONE
from app.core.time_utils import get_timezone, parse_utc, split_at_local_midnights
from app.dashboard.models import DashboardSnapshot
from app.database.repositories.daily_goal_repository import DailyGoalRepository


class DashboardService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        timezone_name: str = DEFAULT_TIMEZONE,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._zone = get_timezone(timezone_name)
        self._now = now_provider or (lambda: datetime.now(self._zone))
        self._goals = DailyGoalRepository(connection)
        self._cache_key: tuple[int, str] | None = None
        self._cache: DashboardSnapshot | None = None

    def snapshot(self) -> DashboardSnapshot:
        now = self._now().astimezone(self._zone)
        today = now.date()
        key = (self._revision(), today.isoformat())
        if self._cache_key == key and self._cache is not None:
            return self._cache
        daily, blocks = self._allocations()
        goal_map = self._goal_map(today)
        yesterday = today - timedelta(days=1)
        monday = today - timedelta(days=today.weekday())
        prior_monday = monday - timedelta(days=7)
        current_week = sum(
            daily.get(monday + timedelta(days=offset), 0) for offset in range(today.weekday() + 1)
        )
        prior_week = sum(
            daily.get(prior_monday + timedelta(days=offset), 0)
            for offset in range(today.weekday() + 1)
        )
        today_blocks = [value for (day, _group), value in blocks.items() if day == today]
        all_blocks = list(blocks.values())
        goal = goal_map.get(today)
        today_focus = daily.get(today, 0)
        ratio = None if goal is None else today_focus / goal if goal else None
        streak = self._streak(today, daily, goal_map)
        snapshot = DashboardSnapshot(
            today.isoformat(),
            today_focus,
            goal,
            ratio,
            daily.get(yesterday, 0),
            current_week,
            prior_week,
            max(today_blocks, default=0),
            max(all_blocks, default=0),
            streak,
            self._motivation(bool(daily), ratio, current_week, prior_week),
            bool(daily),
        )
        self._cache_key = key
        self._cache = snapshot
        return snapshot

    def invalidate(self) -> None:
        self._cache_key = None
        self._cache = None

    def _allocations(self) -> tuple[dict[date, int], dict[tuple[date, str], int]]:
        rows = self._connection.execute(
            """
            SELECT g.segment_id, g.started_at_utc, g.ended_at_utc, g.timezone_name,
                   g.duration_seconds, g.continuity_group_id
            FROM segments g JOIN sessions s ON s.session_id = g.session_id
            WHERE g.counts_as_focus = 1 AND g.ended_at_utc IS NOT NULL
              AND s.status IN ('completed','completed_with_overtime','stopped_early','recovered')
            ORDER BY g.started_at_utc, g.segment_id
            """
        ).fetchall()
        daily: dict[date, int] = defaultdict(int)
        blocks: dict[tuple[date, str], int] = defaultdict(int)
        for row in rows:
            start = parse_utc(row["started_at_utc"])
            end = parse_utc(row["ended_at_utc"])
            parts = split_at_local_midnights(start, end, row["timezone_name"])
            weights = [part.duration_seconds for part in parts]
            durations = self._allocate(int(row["duration_seconds"]), weights)
            group = str(row["continuity_group_id"] or row["segment_id"])
            for part, duration in zip(parts, durations, strict=True):
                day = date.fromisoformat(part.local_date)
                daily[day] += duration
                blocks[(day, group)] += duration
        return dict(daily), dict(blocks)

    def _goal_map(self, through: date) -> dict[date, int]:
        goals = self._goals.list_all()
        if not goals:
            return {}
        first = date.fromisoformat(goals[0].effective_from_date)
        values: dict[date, int] = {}
        cursor = first
        while cursor <= through:
            goal = next(
                (
                    item
                    for item in goals
                    if item.effective_from_date <= cursor.isoformat()
                    and (
                        item.effective_to_date is None
                        or item.effective_to_date >= cursor.isoformat()
                    )
                ),
                None,
            )
            if goal is not None:
                values[cursor] = goal.goal_seconds
            cursor += timedelta(days=1)
        return values

    @staticmethod
    def _streak(today: date, daily: dict[date, int], goals: dict[date, int]) -> int:
        if not goals:
            return 0
        cursor = today
        if cursor in goals and daily.get(cursor, 0) < goals[cursor]:
            cursor -= timedelta(days=1)
        count = 0
        first = min(goals)
        while cursor >= first:
            goal = goals.get(cursor)
            if goal is None or daily.get(cursor, 0) < goal:
                break
            count += 1
            cursor -= timedelta(days=1)
        return count

    @staticmethod
    def _motivation(
        has_history: bool,
        ratio: float | None,
        current_week: int,
        prior_week: int,
    ) -> str:
        if not has_history:
            return "Begin with one focused minute; a small start is still a start."
        if ratio is None:
            return "Set a daily goal that feels useful, then give it one clear block."
        if ratio >= 1:
            return "Daily goal reached. Protect the pace that made it possible."
        if ratio >= 0.75:
            return "You are close to today's goal; one calm block can carry it home."
        if current_week > prior_week:
            return "This week is building steadily. Keep the next block simple."
        return "Choose one concrete task for the next block and let that be enough."

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
        result = [total * weight // weight_total for weight in weights[:-1]]
        result.append(total - sum(result))
        return tuple(result)
