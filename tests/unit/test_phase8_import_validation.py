import csv
import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from app.portability.csv_mapping import portable_row_checksum
from app.portability.import_errors import ImportValidationError
from app.portability.import_models import PortableSourceRow, SourceLocation
from app.portability.import_validator import PortableImportValidator, _session_from_csv
from app.services.data_location_service import resolve_portable_folder
from app.services.session_checksum_service import session_checksum

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PORTABLE_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "portable_data"


def _portable_copy(tmp_path: Path) -> Path:
    target = tmp_path / "portable copy ü"
    shutil.copytree(PORTABLE_FIXTURE, target)
    return target


def _rewrite(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _mutate_first_session(root: Path, mutation) -> None:
    path = next((root / "sessions").rglob("*.csv"))
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or ())
    mutation(rows[0])
    rows[0]["record_checksum"] = session_checksum(_session_from_csv(rows[0]))
    _rewrite(path, rows, fields)


def test_valid_root_and_repository_child_are_resolved(tmp_path: Path) -> None:
    child = tmp_path / "repo with spaces" / "portable_data"
    child.parent.mkdir()
    shutil.copytree(PORTABLE_FIXTURE, child)
    assert resolve_portable_folder(child) == child.resolve()
    assert resolve_portable_folder(child.parent) == child.resolve()
    report, bundle = PortableImportValidator().validate(child.parent)
    assert report.safe and bundle is not None
    assert bundle.summary.counts.sessions >= 1
    assert bundle.summary.counts.logical_segments >= 1
    assert bundle.file_hashes


def test_missing_and_newer_manifest_are_rejected(tmp_path: Path) -> None:
    root = _portable_copy(tmp_path)
    (root / "manifest.json").unlink()
    report, _ = PortableImportValidator().validate(root)
    assert not report.safe and "missing required file" in report.errors[0]

    root = _portable_copy(tmp_path / "newer")
    path = root / "manifest.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["data_schema_version"] = 999
    path.write_text(json.dumps(raw), encoding="utf-8")
    report, _ = PortableImportValidator().validate(root)
    assert not report.safe and "newer than supported" in report.errors[0]

    root = _portable_copy(tmp_path / "bad-json")
    (root / "manifest.json").write_text("[]", encoding="utf-8")
    report, _ = PortableImportValidator().validate(root)
    assert not report.safe and "manifest root" in report.errors[0]
    with pytest.raises(ImportValidationError):
        PortableImportValidator().require(root)


def test_invalid_header_and_intention_column_are_rejected(tmp_path: Path) -> None:
    root = _portable_copy(tmp_path)
    path = root / "devices.csv"
    path.write_text("device_id,intention\n", encoding="utf-8")
    report, _ = PortableImportValidator().validate(root)
    assert not report.safe
    assert "invalid devices CSV" in report.errors[0]


def test_duplicate_across_partition_parts_is_rejected(tmp_path: Path) -> None:
    root = _portable_copy(tmp_path)
    base = next((root / "sessions").rglob("sessions_*.csv"))
    part = base.with_name(base.stem + "_part002.csv")
    shutil.copy2(base, part)
    report, _ = PortableImportValidator().validate(root)
    assert not report.safe
    assert "duplicate sessions ID across files" in report.errors[0]


def test_partition_gaps_and_wrong_month_are_rejected(tmp_path: Path) -> None:
    root = _portable_copy(tmp_path)
    base = next((root / "sessions").rglob("sessions_*.csv"))
    part3 = base.with_name(base.stem + "_part003.csv")
    part3.write_text(base.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    report, _ = PortableImportValidator().validate(root)
    assert not report.safe and "not contiguous" in report.errors[0]

    root = _portable_copy(tmp_path / "month")
    base = next((root / "sessions").rglob("sessions_*.csv"))
    wrong = base.with_name("sessions_2026-06.csv")
    base.rename(wrong)
    report, _ = PortableImportValidator().validate(root)
    assert not report.safe and "wrong monthly partition" in report.errors[0]


def test_segment_checksum_and_aggregate_mismatch_are_rejected(tmp_path: Path) -> None:
    root = _portable_copy(tmp_path)
    path = next((root / "segments").rglob("*.csv"))
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or ())
    rows[0]["duration_seconds"] = str(int(rows[0]["duration_seconds"]) + 1)
    rows[0]["record_checksum"] = portable_row_checksum(rows[0])
    _rewrite(path, rows, fields)
    report, _ = PortableImportValidator().validate(root)
    assert not report.safe
    assert "session aggregate mismatch" in report.errors[0]


def test_category_semantic_conflict_is_structured(tmp_path: Path) -> None:
    root = _portable_copy(tmp_path)
    path = root / "categories.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or ())
    duplicate = dict(rows[0])
    duplicate["category_id"] = str(uuid4())
    duplicate["category_name"] = f"  {rows[0]['category_name'].upper()}  "
    rows.append(duplicate)
    _rewrite(path, rows, fields)
    report, bundle = PortableImportValidator().validate(root)
    assert bundle is not None
    assert not report.safe
    assert report.conflicts[0].entity == "categories"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    (
        (lambda row: row.update(status="running"), "not finalized"),
        (lambda row: row.update(ended_at_utc=""), "no end timestamp"),
        (lambda row: row.update(actual_focus_seconds="999"), "focus formula"),
        (lambda row: row.update(stopped_early_seconds="999"), "stopped-early"),
        (
            lambda row: row.update(
                completed_planned_timer=(
                    "false" if row["completed_planned_timer"] == "true" else "true"
                )
            ),
            "completion flag",
        ),
        (lambda row: row.update(device_id=str(uuid4())), "session device is missing"),
    ),
)
def test_session_semantics_and_references_are_rejected(tmp_path: Path, mutation, expected) -> None:
    root = _portable_copy(tmp_path)
    _mutate_first_session(root, mutation)
    report, _ = PortableImportValidator().validate(root)
    assert not report.safe and expected in report.errors[0]


def test_overlapping_goals_conflict_and_empty_quotes_warn(tmp_path: Path) -> None:
    root = _portable_copy(tmp_path)
    goal_path = root / "daily_goals.csv"
    with goal_path.open(encoding="utf-8", newline="") as handle:
        fields = next(iter(csv.reader(handle)))
    rows = [
        {
            "schema_version": "1",
            "goal_id": str(uuid4()),
            "effective_from_date": "2026-01-01",
            "effective_to_date": "2026-01-31",
            "goal_seconds": "3600",
            "created_at_utc": "2026-01-01T00:00:00Z",
            "updated_at_utc": "2026-01-01T00:00:00Z",
        },
        {
            "schema_version": "1",
            "goal_id": str(uuid4()),
            "effective_from_date": "2026-01-15",
            "effective_to_date": "",
            "goal_seconds": "7200",
            "created_at_utc": "2026-01-01T00:00:00Z",
            "updated_at_utc": "2026-01-01T00:00:00Z",
        },
    ]
    _rewrite(goal_path, rows, fields)
    quote_path = root / "quotes.csv"
    quote_path.write_text(
        quote_path.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8"
    )
    report, bundle = PortableImportValidator().validate(root)
    assert bundle is not None and report.conflicts
    assert report.warnings[0].code == "no_quotes"


def test_midnight_and_legacy_segments_reconstruct_deterministically(tmp_path: Path) -> None:
    session_id = str(uuid4())
    device_id = str(uuid4())
    source_id = str(uuid4())
    common = {
        "schema_version": "1",
        "source_segment_id": source_id,
        "session_id": session_id,
        "device_id": device_id,
        "segment_sequence": "1",
        "segment_type": "focus",
        "timezone_name": "America/New_York",
        "counts_as_focus": "true",
        "pause_classification": "none",
        "breaks_continuity": "false",
        "continuity_group_id": "",
        "pause_grace_threshold_seconds": "10",
        "focus_phase": "planned",
        "end_reason": "manual_stop",
        "created_at_utc": "2026-12-31T23:59:50Z",
    }
    raw_rows = []
    for number, start, end, duration, local_date in (
        (1, "2026-12-31T23:59:50Z", "2027-01-01T00:00:00Z", "10", "2026-12-31"),
        (2, "2027-01-01T00:00:00Z", "2027-01-01T00:00:12Z", "12", "2027-01-01"),
    ):
        values = {
            **common,
            "segment_id": str(uuid4()),
            "midnight_part_number": str(number),
            "started_at_utc": start,
            "ended_at_utc": end,
            "duration_seconds": duration,
            "utc_offset_minutes": "-300",
            "local_date": local_date,
        }
        raw_rows.append(
            PortableSourceRow(
                "segments",
                values["segment_id"],
                values,
                SourceLocation(
                    tmp_path / f"segments_{local_date[:7]}.csv",
                    2,
                ),
                "x" * 64,
            )
        )
    validator = PortableImportValidator()
    logical, id_map = validator.reconstruct_segments(tuple(raw_rows))
    assert len(logical) == 1
    assert logical[0].segment_id == source_id
    assert logical[0].values["duration_seconds"] == 22
    assert set(id_map.values()) == {source_id}

    legacy = raw_rows[0]
    legacy_values = {**legacy.values, "source_segment_id": "", "midnight_part_number": "1"}
    legacy_row = PortableSourceRow(
        legacy.entity, legacy.record_id, legacy_values, legacy.location, legacy.checksum
    )
    first, _ = validator.reconstruct_segments((legacy_row,))
    second, _ = validator.reconstruct_segments((legacy_row,))
    assert first[0].segment_id == second[0].segment_id
