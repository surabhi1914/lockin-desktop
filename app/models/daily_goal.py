"""Historical local daily-focus goal."""

from dataclasses import dataclass
from sqlite3 import Row


@dataclass(frozen=True, slots=True)
class DailyGoal:
    goal_id: str
    effective_from_date: str
    effective_to_date: str | None
    goal_seconds: int
    created_at_utc: str
    updated_at_utc: str

    @classmethod
    def from_row(cls, row: Row) -> "DailyGoal":
        return cls(**dict(row))
