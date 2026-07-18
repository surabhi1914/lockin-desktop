import csv
from dataclasses import replace
from pathlib import Path

import pytest

from app.core.ids import new_uuid4
from app.models.persisted_segment import PersistedSegment
from app.portability.atomic_csv_writer import AtomicCsvWriter
from app.portability.csv_contracts import SESSIONS_HEADER
from app.portability.errors import PortableValidationError
from app.portability.partition_manager import select_partition
from app.portability.segment_csv_mapper import map_segment


def _segment(start: str, end: str, duration: int) -> PersistedSegment:
    return PersistedSegment(
        new_uuid4(),
        1,
        new_uuid4(),
        new_uuid4(),
        1,
        "focus",
        start,
        end,
        "America/New_York",
        -240,
        duration,
        True,
        "none",
        False,
        new_uuid4(),
        10,
        "planned",
        "manual_stop",
        start,
        end,
    )


def test_cross_midnight_rows_have_stable_ids_and_exact_duration() -> None:
    segment = _segment("2026-07-18T03:59:50Z", "2026-07-18T04:00:10Z", 20)
    rows = map_segment(
        segment, "2026-07-18T04:01:00Z", parent_started_at_utc=segment.started_at_utc
    )
    again = map_segment(
        segment, "2026-07-19T04:01:00Z", parent_started_at_utc=segment.started_at_utc
    )
    assert len(rows) == 2
    assert sum(int(row.values["duration_seconds"]) for row in rows) == 20
    assert [row.record_id for row in rows] == [row.record_id for row in again]
    assert [row.local_date for row in rows] == ["2026-07-17", "2026-07-18"]


def test_segment_mapper_rejects_open_and_backwards_segments() -> None:
    segment = _segment("2026-07-18T03:00:00Z", "2026-07-18T03:01:00Z", 60)
    with pytest.raises(PortableValidationError):
        map_segment(
            replace(segment, ended_at_utc=None),
            "2026-07-18T04:00:00Z",
            parent_started_at_utc=segment.started_at_utc,
        )
    with pytest.raises(PortableValidationError):
        map_segment(
            replace(segment, ended_at_utc="2026-07-18T02:00:00Z"),
            "2026-07-18T04:00:00Z",
            parent_started_at_utc=segment.started_at_utc,
        )


def test_partition_selection_includes_new_row_size_and_blocks_bad_header(tmp_path: Path) -> None:
    row = dict.fromkeys(SESSIONS_HEADER, "x")
    directory = tmp_path / "sessions" / "2026"
    directory.mkdir(parents=True)
    base = directory / "sessions_2026-07.csv"
    with base.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow(SESSIONS_HEADER)
    selected = select_partition(
        tmp_path, "sessions", "2026-07-01", max_file_size_bytes=base.stat().st_size + 2, row=row
    )
    assert selected.name == "sessions_2026-07_part002.csv"
    base.write_text("bad,header\n", encoding="utf-8")
    with pytest.raises(Exception, match="invalid header"):
        select_partition(tmp_path, "sessions", "2026-07-01", row=row)


def test_atomic_writer_preserves_existing_file_on_staged_validation_failure(tmp_path: Path) -> None:
    path = tmp_path / "sessions.csv"
    path.write_text(",".join(SESSIONS_HEADER) + "\n", encoding="utf-8")
    before = path.read_bytes()
    writer = AtomicCsvWriter(tmp_path / "backups", retry_delays=())
    with pytest.raises(PortableValidationError):
        writer.replace(path, "sessions", [dict.fromkeys(SESSIONS_HEADER, "")])
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))
