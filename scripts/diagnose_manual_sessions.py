"""Read-only database-path and recent manual-session diagnostics."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.analytics.history_service import HistoryService
from app.core.paths import PathConfig
from app.database.connection import connect_database
from app.database.repositories.session_repository import SessionRepository
from app.services.manual_session_service import ManualSessionService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List recent manual sessions without exposing intention data."
    )
    parser.add_argument("--database", type=Path, help="SQLite database to inspect read-only")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.limit <= 200:
        parser.error("--limit must be from 1 to 200")
    startup_path = (args.database or PathConfig.from_environment().database_path).resolve()
    if not startup_path.is_file():
        print(f"Database not found: {startup_path}")
        return 1
    connection = connect_database(startup_path, read_only=True)
    try:
        device = connection.execute(
            "SELECT device_id FROM devices ORDER BY created_at_utc LIMIT 1"
        ).fetchone()
        device_id = "" if device is None else str(device["device_id"])
        manual = ManualSessionService(connection, device_id)
        repository = SessionRepository(connection)
        history = HistoryService(connection)
        print(f"Application startup database: {startup_path}")
        print(f"ManualSessionService database: {manual.database_path}")
        print(f"SessionRepository database: {repository.database_path}")
        print(f"HistoryQueryService database: {history.database_path}")
        print("Recent manual sessions:")
        rows = connection.execute(
            """
            SELECT s.session_id, s.entry_source, s.category_id,
                   s.category_name_snapshot, s.status, s.completion_reason,
                   s.started_at_local, s.ended_at_local, s.started_at_utc,
                   s.ended_at_utc, s.actual_focus_seconds,
                   s.planned_focus_seconds, s.created_at_utc, s.device_id,
                   (SELECT COUNT(*) FROM segments g
                    WHERE g.session_id=s.session_id) AS segment_count
            FROM sessions s
            WHERE s.entry_source='manual'
            ORDER BY s.created_at_utc DESC, s.session_id DESC
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()
        if not rows:
            print("(none)")
        for row in rows:
            print(
                " | ".join(
                    (
                        f"session_id={row['session_id']}",
                        f"entry_source={row['entry_source']}",
                        f"category_id={row['category_id']}",
                        f"category_name={row['category_name_snapshot']}",
                        f"status={row['status']}",
                        f"completion_reason={row['completion_reason']}",
                        f"local={row['started_at_local']}..{row['ended_at_local']}",
                        f"utc={row['started_at_utc']}..{row['ended_at_utc']}",
                        f"actual_focus_seconds={row['actual_focus_seconds']}",
                        f"planned_focus_seconds={row['planned_focus_seconds']}",
                        f"created_at_utc={row['created_at_utc']}",
                        f"device_id={row['device_id']}",
                        f"segment_count={row['segment_count']}",
                        f"runtime_database={startup_path}",
                    )
                )
            )
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
