"""Explicitly export canonical daily statistics outside portable raw data."""

import argparse
from pathlib import Path

from app.analytics.analytics_service import AnalyticsService
from app.analytics.export_service import StatisticsExportService
from app.analytics.models import AnalyticsFilters
from app.core.paths import PathConfig
from app.database.connection import connect_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="from_date", required=True)
    parser.add_argument("--to", dest="to_date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    config = PathConfig.from_environment()
    connection = connect_database(config.database_path, read_only=True)
    try:
        result = AnalyticsService(connection).calculate(
            AnalyticsFilters(args.from_date, args.to_date)
        )
    finally:
        connection.close()
    exported = StatisticsExportService(config.portable_root).export(result, args.output)
    print(f"Statistics export: {exported.resolve()}")
    print(f"rows={len(result.daily)} focus_seconds={result.total_focus_seconds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
