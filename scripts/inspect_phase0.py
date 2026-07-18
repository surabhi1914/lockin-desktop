"""Print a privacy-safe inspection report for the Phase 0 foundation."""

import csv
import sqlite3
from pathlib import Path

from app.core.paths import PathConfig
from app.database.migrations import current_schema_version
from app.portability.manifest import load_manifest


def _csv_count(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


def main() -> int:
    config = PathConfig.from_environment()
    print(f"Runtime path: {config.runtime_root}")
    print(f"Portable path: {config.portable_root}")
    print(f"Database path: {config.database_path}")
    if not config.database_path.is_file():
        print("Database: missing")
        return 1
    uri = f"file:{config.database_path.as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as connection:
        version = current_schema_version(connection)
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        print(f"Database schema version: {version}")
        print("Tables present: " + ", ".join(tables))
        print("Row counts:")
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            count = connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
            print(f"  {table}: {count}")
    manifest = load_manifest(config.portable_root / "manifest.json")
    print(f"Manifest schema version: {manifest.manifest_schema_version}")
    print(f"Data schema version: {manifest.data_schema_version}")
    csv_files = sorted(
        path.relative_to(config.portable_root) for path in config.portable_root.rglob("*.csv")
    )
    print("CSV files found: " + ", ".join(str(path) for path in csv_files))
    print(f"Starter-category count: {_csv_count(config.portable_root / 'categories.csv')}")
    print(f"Quote count: {_csv_count(config.portable_root / 'quotes.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
