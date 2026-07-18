"""Read-only Phase 6 database-integrity command."""

import sqlite3

from app.core.paths import PathConfig
from app.services.session_integrity_service import verify_session_integrity


def main() -> int:
    path = PathConfig.from_environment().database_path
    if not path.exists():
        print(f"Database not found: {path}")
        return 1
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        report = verify_session_integrity(connection)
    finally:
        connection.close()
    if not report.healthy:
        for error in report.errors:
            print(f"ERROR: {error}")
        return 1
    print("Session database integrity: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
