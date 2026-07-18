import csv
from pathlib import Path

from app.core.ids import new_uuid4
from app.portability.csv_contracts import header_for
from app.portability.csv_validation import validate_csv


def _write(path: Path, header: tuple[str, ...], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _category_row() -> list[str]:
    return [
        "1",
        new_uuid4(),
        "研究",
        "",
        "true",
        "2026-07-16T12:00:00Z",
        "2026-07-16T12:00:00Z",
    ]


def test_valid_starter_files_and_unicode_quote(tmp_path: Path) -> None:
    categories = tmp_path / "categories.csv"
    quotes = tmp_path / "quotes.csv"
    _write(categories, header_for("categories"), [_category_row()])
    _write(
        quotes,
        header_for("quotes"),
        [["q001", "Café focus — 深く進む", "", "focus", "true", "false"]],
    )
    assert validate_csv(categories, "categories") == ()
    assert validate_csv(quotes, "quotes") == ()


def test_header_order_missing_extra_and_duplicate(tmp_path: Path) -> None:
    expected = header_for("devices")
    cases = {
        "order.csv": (expected[1], expected[0], *expected[2:]),
        "missing.csv": expected[:-1],
        "extra.csv": (*expected, "extra"),
        "duplicate.csv": (*expected, expected[-1]),
    }
    expected_codes = {
        "order.csv": "header_order",
        "missing.csv": "missing_header",
        "extra.csv": "unexpected_header",
        "duplicate.csv": "duplicate_header",
    }
    for name, header in cases.items():
        path = tmp_path / name
        _write(path, tuple(header), [])
        codes = {issue.error_code for issue in validate_csv(path, "devices")}
        assert expected_codes[name] in codes


def test_invalid_boolean_uuid_timestamp_and_empty_required(tmp_path: Path) -> None:
    path = tmp_path / "categories.csv"
    row = _category_row()
    row[1] = "invalid"
    row[2] = ""
    row[4] = "TRUE"
    row[5] = "2026-07-16T12:00:00+00:00"
    _write(path, header_for("categories"), [row])
    codes = {issue.error_code for issue in validate_csv(path, "categories")}
    assert {"invalid_uuid", "empty_required", "invalid_boolean", "invalid_timestamp"} <= codes


def test_negative_duration_and_invalid_date(tmp_path: Path) -> None:
    path = tmp_path / "daily_goals.csv"
    row = [
        "1",
        new_uuid4(),
        "2026-02-30",
        "",
        "-1",
        "2026-07-16T12:00:00Z",
        "2026-07-16T12:00:00Z",
    ]
    _write(path, header_for("daily_goals"), [row])
    codes = {issue.error_code for issue in validate_csv(path, "daily_goals")}
    assert "invalid_integer" in codes
    assert "invalid_date" in codes


def test_invalid_checksum_and_enum(tmp_path: Path) -> None:
    header = header_for("segments")
    row = dict.fromkeys(header, "value")
    row.update(
        {
            "schema_version": "1",
            "segment_id": new_uuid4(),
            "source_segment_id": "",
            "session_id": new_uuid4(),
            "device_id": new_uuid4(),
            "segment_sequence": "1",
            "midnight_part_number": "1",
            "segment_type": "invalid",
            "started_at_utc": "2026-07-16T12:00:00Z",
            "ended_at_utc": "",
            "started_at_local": "2026-07-16T08:00:00-04:00",
            "ended_at_local": "",
            "local_date": "2026-07-16",
            "utc_offset_minutes": "-240",
            "duration_seconds": "1",
            "counts_as_focus": "true",
            "pause_duration_seconds": "0",
            "pause_classification": "none",
            "breaks_continuity": "false",
            "continuity_group_id": "",
            "pause_grace_threshold_seconds": "10",
            "focus_phase": "planned",
            "crossed_midnight": "false",
            "end_reason": "",
            "created_at_utc": "2026-07-16T12:00:00Z",
            "exported_at_utc": "2026-07-16T12:00:01Z",
            "record_checksum": "ABC",
        }
    )
    path = tmp_path / "segments.csv"
    _write(path, header, [[row[column] for column in header]])
    codes = {issue.error_code for issue in validate_csv(path, "segments")}
    assert "invalid_checksum" in codes
    assert "invalid_enum" in codes


def test_duplicate_record_ids_and_row_width(tmp_path: Path) -> None:
    path = tmp_path / "categories.csv"
    row = _category_row()
    second = row.copy()
    second[2] = "Other"
    _write(path, header_for("categories"), [row, second, ["too", "short"]])
    codes = [issue.error_code for issue in validate_csv(path, "categories")]
    assert "duplicate_record_id" in codes
    assert "row_width" in codes


def test_empty_missing_and_invalid_utf8_files(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_bytes(b"")
    invalid = tmp_path / "invalid.csv"
    invalid.write_bytes(b"\xff\xfe")
    assert validate_csv(empty, "quotes")[0].error_code == "missing_header"
    assert validate_csv(invalid, "quotes")[0].error_code == "invalid_utf8"
    assert validate_csv(tmp_path / "missing.csv", "quotes")[0].error_code == "file_missing"
