"""Daily-goal persistence without transaction ownership."""

import sqlite3
from collections.abc import Mapping

from app.models.daily_goal import DailyGoal


class DailyGoalRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_all(self) -> tuple[DailyGoal, ...]:
        return tuple(
            DailyGoal.from_row(row)
            for row in self.connection.execute(
                "SELECT * FROM daily_goals ORDER BY effective_from_date, goal_id"
            )
        )

    def effective_on(self, local_date: str) -> DailyGoal | None:
        row = self.connection.execute(
            """
            SELECT * FROM daily_goals
            WHERE effective_from_date <= ?
              AND (effective_to_date IS NULL OR effective_to_date >= ?)
            ORDER BY effective_from_date DESC LIMIT 1
            """,
            (local_date, local_date),
        ).fetchone()
        return None if row is None else DailyGoal.from_row(row)

    def insert(self, values: Mapping[str, object]) -> None:
        columns = tuple(values)
        placeholders = ", ".join("?" for _ in columns)
        self.connection.execute(
            f"INSERT INTO daily_goals ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values[column] for column in columns),
        )

    def update(self, goal_id: str, values: Mapping[str, object]) -> None:
        assignments = ", ".join(f"{column}=?" for column in values)
        cursor = self.connection.execute(
            f"UPDATE daily_goals SET {assignments} WHERE goal_id=?",
            (*values.values(), goal_id),
        )
        if cursor.rowcount != 1:
            raise LookupError(f"daily goal not found: {goal_id}")
