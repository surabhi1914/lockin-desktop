"""Historical daily-goal changes coordinated across SQLite and portable CSV."""

import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from app.core.constants import DATA_SCHEMA_VERSION
from app.core.ids import new_uuid4
from app.core.time_utils import format_utc, utc_now, validate_date
from app.database.repositories.daily_goal_repository import DailyGoalRepository
from app.models.daily_goal import DailyGoal
from app.portability.atomic_csv_writer import AtomicCsvWriter

GoalListener = Callable[[], None]


class DailyGoalService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        portable_path: Path,
        backup_root: Path,
        *,
        today_provider: Callable[[], date] = date.today,
        timestamp_provider: Callable[[], str] | None = None,
        uuid_provider: Callable[[], str] = new_uuid4,
    ) -> None:
        self._connection = connection
        self.repository = DailyGoalRepository(connection)
        self._path = portable_path
        self._writer = AtomicCsvWriter(backup_root)
        self._today = today_provider
        self._timestamp = timestamp_provider or (lambda: format_utc(utc_now()))
        self._uuid = uuid_provider
        self._listeners: list[GoalListener] = []

    def list_all(self) -> tuple[DailyGoal, ...]:
        return self.repository.list_all()

    def effective_on(self, local_date: date | str) -> DailyGoal | None:
        value = local_date.isoformat() if isinstance(local_date, date) else local_date
        validate_date(value)
        return self.repository.effective_on(value)

    def set_goal(self, goal_seconds: int, effective_from: date | str) -> DailyGoal:
        if isinstance(goal_seconds, bool) or not isinstance(goal_seconds, int):
            raise ValueError("daily goal seconds must be an integer")
        if not 60 <= goal_seconds <= 7 * 24 * 60 * 60:
            raise ValueError("daily goal must be from one minute to seven days")
        start = validate_date(
            effective_from.isoformat() if isinstance(effective_from, date) else effective_from
        )
        if start < self._today():
            raise ValueError("daily goal changes can be effective today or in the future")
        original = self.repository.list_all()
        timestamp = self._timestamp()
        exact = next(
            (goal for goal in original if goal.effective_from_date == start.isoformat()), None
        )
        if exact is not None:
            intended = tuple(
                replace(goal, goal_seconds=goal_seconds, updated_at_utc=timestamp)
                if goal.goal_id == exact.goal_id
                else goal
                for goal in original
            )
            result = next(goal for goal in intended if goal.goal_id == exact.goal_id)
        else:
            next_goal = next(
                (goal for goal in original if goal.effective_from_date > start.isoformat()), None
            )
            containing = next(
                (
                    goal
                    for goal in original
                    if goal.effective_from_date < start.isoformat()
                    and (
                        goal.effective_to_date is None
                        or goal.effective_to_date >= start.isoformat()
                    )
                ),
                None,
            )
            result = DailyGoal(
                self._uuid(),
                start.isoformat(),
                None
                if next_goal is None
                else (
                    date.fromisoformat(next_goal.effective_from_date) - timedelta(days=1)
                ).isoformat(),
                goal_seconds,
                timestamp,
                timestamp,
            )
            intended_list = list(original)
            if containing is not None:
                intended_list = [
                    replace(
                        goal,
                        effective_to_date=(start - timedelta(days=1)).isoformat(),
                        updated_at_utc=timestamp,
                    )
                    if goal.goal_id == containing.goal_id
                    else goal
                    for goal in intended_list
                ]
            intended_list.append(result)
            intended = tuple(sorted(intended_list, key=lambda goal: goal.effective_from_date))
        replaced_csv = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            if exact is not None:
                self.repository.update(
                    exact.goal_id,
                    {"goal_seconds": goal_seconds, "updated_at_utc": timestamp},
                )
            else:
                prior = next(
                    (
                        goal
                        for goal in original
                        if goal.effective_from_date < start.isoformat()
                        and (
                            goal.effective_to_date is None
                            or goal.effective_to_date >= start.isoformat()
                        )
                    ),
                    None,
                )
                if prior is not None:
                    self.repository.update(
                        prior.goal_id,
                        {
                            "effective_to_date": (start - timedelta(days=1)).isoformat(),
                            "updated_at_utc": timestamp,
                        },
                    )
                self.repository.insert(self._values(result))
            self._write(intended)
            replaced_csv = True
            self._connection.commit()
        except (sqlite3.Error, OSError, RuntimeError, ValueError, LookupError) as exc:
            if self._connection.in_transaction:
                self._connection.rollback()
            if replaced_csv:
                self._write(original)
            raise RuntimeError(f"daily goal update was not applied: {exc}") from exc
        for listener in tuple(self._listeners):
            listener()
        return result

    def subscribe(self, listener: GoalListener) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def _write(self, goals: tuple[DailyGoal, ...]) -> None:
        self._writer.replace(
            self._path,
            "daily_goals",
            (
                {
                    "schema_version": str(DATA_SCHEMA_VERSION),
                    "goal_id": goal.goal_id,
                    "effective_from_date": goal.effective_from_date,
                    "effective_to_date": goal.effective_to_date or "",
                    "goal_seconds": str(goal.goal_seconds),
                    "created_at_utc": goal.created_at_utc,
                    "updated_at_utc": goal.updated_at_utc,
                }
                for goal in goals
            ),
        )

    @staticmethod
    def _values(goal: DailyGoal) -> dict[str, object]:
        return {
            "goal_id": goal.goal_id,
            "effective_from_date": goal.effective_from_date,
            "effective_to_date": goal.effective_to_date,
            "goal_seconds": goal.goal_seconds,
            "created_at_utc": goal.created_at_utc,
            "updated_at_utc": goal.updated_at_utc,
        }
