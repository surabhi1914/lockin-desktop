"""Read-only provenance and structure verification for manual sessions."""

import csv

from app.core.paths import PathConfig
from app.database.connection import connect_database
from app.services.session_integrity_service import verify_session_integrity


def main() -> int:
    config = PathConfig.from_environment()
    if not config.database_path.is_file():
        print("Manual session verification: no runtime database")
        return 0
    connection = connect_database(config.database_path, read_only=True)
    errors: list[str] = []
    try:
        integrity = verify_session_integrity(connection)
        errors.extend(integrity.errors)
        rows = connection.execute(
            "SELECT session_id FROM sessions WHERE entry_source='manual' ORDER BY session_id"
        ).fetchall()
        portable_sources: dict[str, str] = {}
        for path in sorted((config.portable_root / "sessions").glob("*/*.csv")):
            with path.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    portable_sources[row["session_id"]] = row.get("entry_source", "")
        for row in rows:
            session_id = str(row["session_id"])
            ledger = connection.execute(
                """
                SELECT 1 FROM sync_ledger
                WHERE record_type='session' AND record_id=?
                """,
                (session_id,),
            ).fetchone()
            if ledger is not None and portable_sources.get(session_id) != "manual":
                errors.append(f"manual session {session_id} portable source does not match SQLite")
    finally:
        connection.close()
    if errors:
        print("Manual session verification: FAILED")
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Manual session verification: OK ({len(rows)} manual session(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
