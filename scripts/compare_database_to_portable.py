"""Read-only SQLite-to-portable import and ledger comparison."""

import argparse
from pathlib import Path

from app.portability.database_portable_comparator import compare_database_to_portable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare imported SQLite with portable history")
    parser.add_argument("--portable-root", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args(argv)
    report = compare_database_to_portable(args.database, args.portable_root)
    print(f"healthy: {str(report.healthy).lower()}")
    print(f"missing_in_database: {report.missing_in_database}")
    print(f"missing_in_portable: {report.missing_in_portable}")
    print(f"checksum_conflicts: {report.conflicts}")
    print(f"ledger_mismatches: {report.ledger_mismatches}")
    for error in report.errors:
        print(f"ERROR: {error}")
    return 0 if report.healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
