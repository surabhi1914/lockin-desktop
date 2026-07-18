"""Generate deterministic sanitized starter resources without reading live portable data."""

import argparse
import csv
import json
import shutil
from pathlib import Path

from app.bootstrap import STARTER_CATEGORIES, STARTER_QUOTES
from app.core.constants import (
    APPLICATION_NAME,
    DATA_SCHEMA_VERSION,
    DEFAULT_PARTITION_SIZE_BYTES,
    MANIFEST_SCHEMA_VERSION,
)
from app.core.ids import starter_category_uuid
from app.portability.csv_contracts import header_for
from app.portability.manifest import EXPECTED_ENTITIES

FIXED_TIMESTAMP = "2000-01-01T00:00:00Z"


def prepare(destination: Path) -> None:
    destination = destination.resolve()
    if destination.exists():
        shutil.rmtree(destination)
    (destination / "templates").mkdir(parents=True)
    manifest = {
        "application": APPLICATION_NAME,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "data_schema_version": DATA_SCHEMA_VERSION,
        "created_at_utc": FIXED_TIMESTAMP,
        "updated_at_utc": FIXED_TIMESTAMP,
        "last_successful_sync_at_utc": None,
        "primary_timezone": "America/Detroit",
        "csv_encoding": "utf-8",
        "duration_unit": "seconds",
        "boolean_encoding": "true_false_lowercase",
        "partitioning": {
            "strategy": "monthly_then_size",
            "max_file_size_bytes": DEFAULT_PARTITION_SIZE_BYTES,
            "part_number_width": 3,
        },
        "entities": EXPECTED_ENTITIES,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write(destination / "devices.csv", "devices", ())
    _write(destination / "daily_goals.csv", "daily_goals", ())
    _write(
        destination / "categories.csv",
        "categories",
        (
            (
                str(DATA_SCHEMA_VERSION),
                starter_category_uuid(name),
                name,
                "",
                "true",
                FIXED_TIMESTAMP,
                FIXED_TIMESTAMP,
            )
            for name in STARTER_CATEGORIES
        ),
    )
    _write(
        destination / "quotes.csv",
        "quotes",
        (
            (f"q{number:03d}", quote, "", "focus", "true", "false")
            for number, quote in enumerate(STARTER_QUOTES, start=1)
        ),
    )
    for entity in ("sessions", "segments", "distractions"):
        _write(destination / "templates" / f"{entity}.csv", entity, ())


def _write(path: Path, entity: str, rows: object) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header_for(entity))
        writer.writerows(rows)  # type: ignore[arg-type]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "packaging" / "starter_resources",
    )
    args = parser.parse_args(argv)
    prepare(args.output)
    print(f"Sanitized starter resources: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
