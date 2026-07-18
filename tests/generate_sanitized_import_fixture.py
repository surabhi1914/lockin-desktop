"""Generate synthetic portable history used by clean-checkout import tests."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.bootstrap import run_phase0_bootstrap
from app.core.ids import starter_category_uuid
from app.core.paths import PathConfig
from app.portability.import_validator import PortableImportValidator
from app.services.distraction_marker_service import DistractionMarkerService
from app.services.portable_sync_service import PortableSyncService
from app.timer import TimerSnapshot
from tests.integration.test_phase6_session_persistence import Harness


def generate(output: Path, *, replace_existing: bool = False) -> None:
    """Create one clearly synthetic finalized session with a distraction."""
    if output.exists():
        permitted_root = (REPOSITORY_ROOT / "tests" / "fixtures").resolve()
        if not replace_existing or permitted_root not in output.parents:
            raise FileExistsError(f"Refusing to overwrite existing fixture: {output}")
        shutil.rmtree(output)
    with tempfile.TemporaryDirectory(prefix="lockin-synthetic-import-") as temporary:
        runtime = Path(temporary) / "runtime"
        config = PathConfig(REPOSITORY_ROOT, runtime, output)
        bootstrap = run_phase0_bootstrap(config=config)
        if not bootstrap.success:
            raise RuntimeError("Synthetic fixture bootstrap failed: " + "; ".join(bootstrap.errors))
        _append_synthetic_category(output / "categories.csv")

        harness = Harness(runtime)
        original_category_id = harness.category_id
        harness.category_id = starter_category_uuid("Research")
        harness.connection.execute(
            "DELETE FROM categories WHERE category_id = ?", (original_category_id,)
        )
        harness.connection.execute(
            "INSERT INTO categories VALUES (?, 'Research', NULL, 1, ?, ?)",
            (harness.category_id, harness.category.created_at_utc, harness.category.updated_at_utc),
        )
        harness.connection.commit()
        harness.category = replace(harness.category, category_id=harness.category_id)
        harness.draft = replace(harness.draft, category_id=harness.category_id)

        context = harness.start()
        snapshot = harness.advance(2)
        _record_distraction(harness, snapshot)
        harness.service.pause(harness.engine.pause())
        harness.advance(2)
        harness.service.finalize(harness.engine.stop(), "manual_stop")
        sync = PortableSyncService(
            harness.connection,
            output,
            runtime / "portable_backups",
        ).sync_session(context.session_id)
        harness.connection.close()
        if not sync.success:
            raise RuntimeError("Synthetic fixture sync failed: " + "; ".join(sync.errors))

    report, bundle = PortableImportValidator().validate(output)
    if not report.safe or bundle is None:
        raise RuntimeError("Synthetic fixture validation failed: " + "; ".join(report.errors))
    counts = bundle.summary.counts
    if counts.sessions != 1 or counts.logical_segments < 1 or counts.distractions != 1:
        raise RuntimeError(f"Unexpected synthetic fixture counts: {counts}")
    for path in output.rglob("*"):
        if path.is_file() and "Never persist this intention" in path.read_text(encoding="utf-8"):
            raise RuntimeError(f"Temporary intention leaked into synthetic fixture: {path}")


def _record_distraction(harness: Harness, snapshot: TimerSnapshot) -> None:
    markers = DistractionMarkerService()
    markers.mark(
        snapshot,
        harness.category,
        before_append=lambda marker: harness.service.record_distraction(marker, snapshot),
    )


def _append_synthetic_category(path: Path) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or ())
    timestamp = rows[0]["created_at_utc"]
    rows.append(
        {
            "schema_version": "1",
            "category_id": starter_category_uuid("Synthetic Planning"),
            "category_name": "Synthetic Planning",
            "category_icon": "",
            "is_active": "true",
            "created_at_utc": timestamp,
            "updated_at_utc": timestamp,
        }
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "tests" / "fixtures" / "portable_data",
    )
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    generate(args.output.resolve(), replace_existing=args.replace)
    print(f"Sanitized import fixture: OK ({args.output.resolve()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
