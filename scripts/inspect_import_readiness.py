"""Read-only Phase 8 portable import-readiness inspection."""

import argparse
from dataclasses import asdict
from pathlib import Path

from app.portability.import_validator import PortableImportValidator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect portable data for safe import")
    parser.add_argument("--portable-root", required=True, type=Path)
    args = parser.parse_args(argv)
    report, bundle = PortableImportValidator().validate(args.portable_root)
    print(f"schema_compatible: {str(bundle is not None).lower()}")
    if report.summary is not None:
        summary = report.summary
        print(f"portable_root: {summary.portable_root}")
        print(f"files: {summary.file_count}")
        for name, value in asdict(summary.counts).items():
            print(f"{name}: {value}")
        print(
            f"date_range: {summary.earliest_local_date or '-'} to "
            f"{summary.latest_local_date or '-'}"
        )
        print("devices: " + (", ".join(summary.device_labels) or "-"))
    print(f"duplicates_or_conflicts: {len(report.conflicts)}")
    print(f"warnings: {len(report.warnings)}")
    print(f"recommended_mode: {report.recommended_mode.value}")
    print(f"safe_to_import: {str(report.safe).lower()}")
    for error in report.errors:
        print(f"ERROR: {error}")
    for conflict in report.conflicts:
        print(f"CONFLICT: {conflict.entity} {conflict.record_id}: {conflict.reason}")
    for warning in report.warnings:
        print(f"WARNING: {warning.message}")
    return 0 if report.safe else 1


if __name__ == "__main__":
    raise SystemExit(main())
