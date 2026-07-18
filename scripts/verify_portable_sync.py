"""Read-only portable CSV and SQLite/ledger verification command."""

import sqlite3

from app.core.paths import PathConfig
from app.services.portable_verification_service import PortableVerificationService


def main() -> int:
    config = PathConfig.from_environment()
    if not config.database_path.exists():
        print(f"Database not found: {config.database_path}")
        return 1
    connection = sqlite3.connect(f"file:{config.database_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        report = PortableVerificationService(
            connection, config.portable_root, config.runtime_root / "portable_backups"
        ).verify()
    finally:
        connection.close()
    print(f"Portable verification: {'OK' if report.healthy else 'FAILED'}")
    print(
        f"checked_files={len(report.checked_files)} pending={report.pending} stale={report.stale}"
    )
    for error in report.errors:
        print(f"ERROR: {error}")
    return 0 if report.healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
