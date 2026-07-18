"""Read-only overview of Phase 7 portable files and sync-ledger state."""

import sqlite3

from app.core.paths import PathConfig
from app.services.portable_verification_service import count_portable_rows


def main() -> int:
    config = PathConfig.from_environment()
    if not config.database_path.exists():
        print(f"Database not found: {config.database_path}")
        return 1
    counts = count_portable_rows(config.portable_root)
    connection = sqlite3.connect(f"file:{config.database_path.as_posix()}?mode=ro", uri=True)
    try:
        ledger = int(connection.execute("SELECT COUNT(*) FROM sync_ledger").fetchone()[0])
    finally:
        connection.close()
    for entity, count in counts.items():
        print(f"{entity}: {count}")
    print(f"sync_ledger: {ledger}")
    print(f"portable_root: {config.portable_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
