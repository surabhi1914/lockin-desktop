"""Read-only overview of Phase 6 local session persistence."""

import sqlite3
from pathlib import Path

from app.core.paths import PathConfig


def _connect_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def main() -> int:
    path = PathConfig.from_environment().database_path
    if not path.exists():
        print(f"Database not found: {path}")
        return 1
    with _connect_read_only(path) as connection:
        counts = {
            "devices": connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0],
            "finalized": connection.execute(
                "SELECT COUNT(*) FROM sessions WHERE ended_at_utc IS NOT NULL"
            ).fetchone()[0],
            "unresolved": connection.execute(
                "SELECT COUNT(*) FROM runtime_session_state"
            ).fetchone()[0],
            "segments": connection.execute("SELECT COUNT(*) FROM segments").fetchone()[0],
            "distractions": connection.execute("SELECT COUNT(*) FROM distractions").fetchone()[0],
            "open_segments": connection.execute(
                "SELECT COUNT(*) FROM segments WHERE ended_at_utc IS NULL"
            ).fetchone()[0],
        }
        for name, value in counts.items():
            print(f"{name}: {value}")
        print("latest finalized sessions:")
        for row in connection.execute(
            """
            SELECT started_at_local, category_name_snapshot, actual_focus_seconds,
                   overtime_seconds, status FROM sessions
            WHERE ended_at_utc IS NOT NULL ORDER BY started_at_utc DESC LIMIT 5
            """
        ):
            print(
                f"- {row['started_at_local']} | {row['category_name_snapshot']} | "
                f"focus={row['actual_focus_seconds']}s | overtime={row['overtime_seconds']}s | "
                f"{row['status']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
