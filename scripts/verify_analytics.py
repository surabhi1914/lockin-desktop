"""Read-only canonical analytics and query-plan verification."""

from datetime import date, timedelta

from app.analytics.analytics_service import AnalyticsService
from app.analytics.models import AnalyticsFilters
from app.core.paths import PathConfig
from app.database.connection import connect_database


def main() -> int:
    config = PathConfig.from_environment()
    if not config.database_path.is_file():
        print("Analytics verification: no runtime database")
        return 0
    connection = connect_database(config.database_path, read_only=True)
    try:
        today = date.today()
        result = AnalyticsService(connection).calculate(
            AnalyticsFilters((today - timedelta(days=29)).isoformat(), today.isoformat())
        )
        plans = connection.execute(
            """
            EXPLAIN QUERY PLAN SELECT s.session_id FROM sessions s
            WHERE s.status IN ('completed','completed_with_overtime','stopped_early','recovered')
              AND s.local_date_started BETWEEN ? AND ?
            """,
            ((today - timedelta(days=36)).isoformat(), today.isoformat()),
        ).fetchall()
    finally:
        connection.close()
    if any(
        value < 0
        for value in (
            result.total_focus_seconds,
            result.total_pause_seconds,
            result.distraction_count,
            result.session_count,
        )
    ):
        print("Analytics verification: FAILED (negative metric)")
        return 1
    print("Analytics verification: OK")
    print(
        f"days={len(result.daily)} focus={result.total_focus_seconds} "
        f"sessions={result.session_count} pauses={result.total_pause_seconds} "
        f"distractions={result.distraction_count}"
    )
    print("query_plan=" + " | ".join(str(row[3]) for row in plans))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
