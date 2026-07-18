"""Read-only motivational dashboard correctness smoke check."""

from app.core.paths import PathConfig
from app.dashboard.dashboard_service import DashboardService
from app.database.connection import connect_database


def main() -> int:
    config = PathConfig.from_environment()
    if not config.database_path.is_file():
        print("Dashboard verification: no runtime database")
        return 0
    connection = connect_database(config.database_path, read_only=True)
    try:
        snapshot = DashboardService(connection).snapshot()
    finally:
        connection.close()
    print("Dashboard verification: OK")
    print(
        f"date={snapshot.local_date} today_focus={snapshot.today_focus_seconds} "
        f"week_focus={snapshot.current_week_seconds} streak={snapshot.goal_streak_days}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
