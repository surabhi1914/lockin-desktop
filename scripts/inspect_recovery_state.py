"""Privacy-safe read-only recovery inspection."""

import argparse
from pathlib import Path

from app.core.paths import PathConfig
from app.database.connection import connect_database
from app.recovery.recovery_analyzer import RecoveryAnalyzer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect unfinished recovery state")
    parser.add_argument("--runtime-root", type=Path)
    args = parser.parse_args(argv)
    runtime = args.runtime_root or PathConfig.from_environment().runtime_root
    database = runtime / "lockin.sqlite3"
    if not database.is_file():
        print("recovery_states: 0")
        return 0
    connection = connect_database(database, read_only=True)
    try:
        analyses = RecoveryAnalyzer(connection).analyze_all()
    finally:
        connection.close()
    print(f"recovery_states: {len(analyses)}")
    for item in analyses:
        print(
            f"{item.session_id[:8]} state={item.original_timer_state} "
            f"confirmed_focus={item.confirmed_focus_seconds} "
            f"unknown={item.unknown_gap_seconds} "
            f"resumable={str(item.can_resume_after_sleep).lower()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
