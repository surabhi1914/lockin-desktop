import csv
from datetime import date
from pathlib import Path

import pytest

from app.analytics.analytics_service import AnalyticsService
from app.analytics.date_presets import DatePreset, preset_range
from app.analytics.export_service import EXPORT_HEADER, StatisticsExportService
from app.analytics.history_service import HistoryFilters, HistoryService
from app.analytics.models import AnalyticsFilters
from app.core.ids import new_uuid4
from app.database.migrations import initialize_database


def _base(tmp_path: Path):
    connection = initialize_database(tmp_path / "lockin.sqlite3")
    stamp = "2026-01-01T12:00:00Z"
    devices = (new_uuid4(), new_uuid4())
    categories = (new_uuid4(), new_uuid4())
    for index, device in enumerate(devices):
        connection.execute(
            "INSERT INTO devices VALUES (?, ?, ?, ?)",
            (device, f"Device {index + 1}", stamp, stamp),
        )
    for index, category in enumerate(categories):
        connection.execute(
            "INSERT INTO categories VALUES (?, ?, NULL, 1, ?, ?)",
            (category, f"Category {index + 1}", stamp, stamp),
        )
    return connection, devices, categories


def _session(
    connection,
    device: str,
    category: str,
    *,
    sequence: int,
    local_date: str,
    start: str,
    status: str,
    planned: int,
    planned_completed: int,
    overtime: int = 0,
    pause: int = 0,
    distractions: int = 0,
    segments: tuple[tuple[str, str, int, str, str], ...] = (),
) -> str:
    session_id = new_uuid4()
    end = segments[-1][1] if segments else start
    values = {
        "session_id": session_id,
        "schema_version": 1,
        "device_id": device,
        "session_sequence": sequence,
        "category_id": category,
        "category_name_snapshot": "Fixture",
        "local_date_started": local_date,
        "timezone_name": "America/Detroit",
        "utc_offset_started_minutes": -240,
        "started_at_utc": start,
        "started_at_local": start.replace("Z", "-04:00"),
        "ended_at_utc": end,
        "ended_at_local": end.replace("Z", "-04:00"),
        "planned_focus_seconds": planned,
        "actual_focus_seconds": planned_completed + overtime,
        "planned_focus_completed_seconds": planned_completed,
        "overtime_seconds": overtime,
        "total_pause_seconds": pause,
        "wall_clock_seconds": planned_completed + overtime + pause,
        "pause_count": int(pause > 0),
        "short_pause_count": int(0 < pause <= 10),
        "long_pause_count": int(pause > 10),
        "distraction_count": distractions,
        "status": status,
        "completion_reason": "timer_completed",
        "stopped_early_seconds": max(0, planned - planned_completed),
        "completed_planned_timer": int(planned_completed == planned),
        "created_at_utc": start,
        "updated_at_utc": end,
        "record_checksum": "checksum",
    }
    columns = tuple(values)
    connection.execute(
        f"INSERT INTO sessions ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
        tuple(values[column] for column in columns),
    )
    group = new_uuid4()
    for index, (seg_start, seg_end, duration, kind, classification) in enumerate(segments, start=1):
        focus = kind in {"planned", "overtime"}
        connection.execute(
            """
            INSERT INTO segments(
              segment_id,schema_version,session_id,device_id,segment_sequence,segment_type,
              started_at_utc,ended_at_utc,timezone_name,utc_offset_started_minutes,
              duration_seconds,counts_as_focus,pause_classification,breaks_continuity,
              continuity_group_id,pause_grace_threshold_seconds,focus_phase,end_reason,
              created_at_utc,updated_at_utc
            ) VALUES (?,1,?,?,?, ?,?,?,'America/Detroit',-240,?,?,?,?,?,10,?,'fixture',?,?)
            """,
            (
                new_uuid4(),
                session_id,
                device,
                index,
                "focus" if focus else "pause",
                seg_start,
                seg_end,
                duration,
                int(focus),
                "none" if focus else classification,
                int(classification in {"continuity_break", "system_sleep"}),
                group,
                kind if focus else "not_applicable",
                seg_start,
                seg_end,
            ),
        )
    for index in range(distractions):
        connection.execute(
            """
            INSERT INTO distractions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                new_uuid4(),
                1,
                session_id,
                None,
                device,
                start,
                start.replace("Z", "-04:00"),
                local_date,
                "America/Detroit",
                category,
                "Fixture",
                index + 1,
                max(0, planned - index),
                0,
                None,
                start,
            ),
        )
    return session_id


def _fixture(tmp_path: Path):
    connection, devices, categories = _base(tmp_path)
    _session(
        connection,
        devices[0],
        categories[0],
        sequence=1,
        local_date="2026-07-17",
        start="2026-07-17T14:00:00Z",
        status="completed",
        planned=1800,
        planned_completed=1800,
        segments=(("2026-07-17T14:00:00Z", "2026-07-17T14:30:00Z", 1800, "planned", "none"),),
    )
    _session(
        connection,
        devices[0],
        categories[0],
        sequence=2,
        local_date="2026-07-17",
        start="2026-07-17T15:00:00Z",
        status="completed_with_overtime",
        planned=1200,
        planned_completed=1200,
        overtime=600,
        pause=120,
        distractions=2,
        segments=(
            ("2026-07-17T15:00:00Z", "2026-07-17T15:20:00Z", 1200, "planned", "none"),
            ("2026-07-17T15:20:00Z", "2026-07-17T15:22:00Z", 120, "pause", "system_sleep"),
            ("2026-07-17T15:22:00Z", "2026-07-17T15:32:00Z", 600, "overtime", "none"),
        ),
    )
    _session(
        connection,
        devices[1],
        categories[1],
        sequence=1,
        local_date="2026-07-16",
        start="2026-07-17T03:30:00Z",
        status="stopped_early",
        planned=3600,
        planned_completed=1800,
        segments=(("2026-07-17T03:30:00Z", "2026-07-17T04:30:00Z", 1800, "planned", "none"),),
    )
    _session(
        connection,
        devices[1],
        categories[1],
        sequence=2,
        local_date="2026-07-17",
        start="2026-07-17T17:00:00Z",
        status="recovered",
        planned=1200,
        planned_completed=600,
        segments=(("2026-07-17T17:00:00Z", "2026-07-17T17:10:00Z", 600, "planned", "none"),),
    )
    _session(
        connection,
        devices[0],
        categories[0],
        sequence=3,
        local_date="2026-07-17",
        start="2026-07-17T18:00:00Z",
        status="discarded",
        planned=600,
        planned_completed=600,
        segments=(("2026-07-17T18:00:00Z", "2026-07-17T18:10:00Z", 600, "planned", "none"),),
    )
    stamp = "2026-07-01T00:00:00Z"
    connection.execute(
        "INSERT INTO daily_goals VALUES (?, '2026-07-01', NULL, 1800, ?, ?)",
        (new_uuid4(), stamp, stamp),
    )
    connection.commit()
    return connection, devices, categories


def test_every_statistics_family_and_local_midnight_allocation(tmp_path: Path) -> None:
    connection, devices, _categories = _fixture(tmp_path)
    result = AnalyticsService(connection, current_device_id=devices[0]).calculate(
        AnalyticsFilters("2026-07-16", "2026-07-17")
    )
    assert result.total_focus_seconds == 6000
    assert [row.focus_seconds for row in result.daily] == [900, 5100]
    assert result.active_days == 2 and result.goal_met_days == 1
    assert result.session_count == 4
    assert dict(result.sessions_by_status) == {
        "completed": 1,
        "completed_with_overtime": 1,
        "recovered": 1,
        "stopped_early": 1,
    }
    assert result.completion_rate == 0.5
    assert result.planned_seconds == 7800
    assert result.planned_completed_seconds == 5400
    assert result.stopped_early_seconds == 2400
    assert result.overtime_seconds == 600
    assert result.block_count == 4 and result.longest_block_seconds == 1800
    assert result.total_pause_seconds == 120
    assert result.pause_count == 1 and result.system_sleep_pause_count == 1
    assert result.distraction_count == 2 and result.sessions_with_distractions == 1
    assert len(result.categories) == 2 and len(result.devices) == 2
    assert result.devices[0].is_current_device
    assert sum(count for _bucket, count in result.block_buckets) == result.block_count


def test_statistics_filters_overtime_recovered_category_device_status_and_minimum(
    tmp_path: Path,
) -> None:
    connection, devices, categories = _fixture(tmp_path)
    service = AnalyticsService(connection)
    no_extra = service.calculate(
        AnalyticsFilters(
            "2026-07-17",
            "2026-07-17",
            include_overtime=False,
            include_recovered=False,
        )
    )
    assert no_extra.total_focus_seconds == 3900
    selected = service.calculate(
        AnalyticsFilters(
            "2026-07-17",
            "2026-07-17",
            category_ids=(categories[0],),
            statuses=("completed_with_overtime",),
            device_ids=(devices[0],),
            minimum_focus_seconds=1500,
        )
    )
    assert selected.session_count == 1 and selected.total_focus_seconds == 1800


def test_history_filters_pagination_detail_and_no_intention(tmp_path: Path) -> None:
    connection, devices, categories = _fixture(tmp_path)
    for index in range(55):
        _session(
            connection,
            devices[0],
            categories[0],
            sequence=10 + index,
            local_date="2026-07-15",
            start=f"2026-07-15T{index % 24:02d}:00:00Z",
            status="completed",
            planned=60,
            planned_completed=60,
            segments=(),
        )
    connection.commit()
    history = HistoryService(connection)
    first = history.search(HistoryFilters(page_size=50))
    second = history.search(HistoryFilters(page=2, page_size=50))
    assert first.total_count == 59 and len(first.rows) == 50 and len(second.rows) == 9
    filtered = history.search(
        HistoryFilters(
            category_ids=(categories[1],),
            device_ids=(devices[1],),
            statuses=("recovered",),
            minimum_focus_seconds=500,
            maximum_focus_seconds=700,
        )
    )
    assert len(filtered.rows) == 1
    detail = history.detail(filtered.rows[0].session_id)
    assert detail.session.status == "recovered" and detail.recovery_events == ()
    assert "intention" not in repr(detail).casefold()


def test_statistics_export_is_explicit_atomic_and_outside_portable(tmp_path: Path) -> None:
    connection, _devices, _categories = _fixture(tmp_path)
    result = AnalyticsService(connection).calculate(AnalyticsFilters("2026-07-16", "2026-07-17"))
    portable = tmp_path / "portable"
    exporter = StatisticsExportService(portable)
    destination = tmp_path / "reports" / "statistics.csv"
    assert exporter.export(result, destination) == destination
    with destination.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == EXPORT_HEADER
        assert len(list(reader)) == 2
    with pytest.raises(ValueError, match="outside portable"):
        exporter.export(result, portable / "statistics.csv")


def test_date_presets_include_leap_and_monday_boundaries() -> None:
    today = date(2024, 3, 1)
    assert preset_range(DatePreset.LAST_7_DAYS, today) == (date(2024, 2, 24), today)
    assert preset_range(DatePreset.THIS_WEEK, today)[0].weekday() == 0
    assert preset_range(DatePreset.LAST_MONTH, today) == (
        date(2024, 2, 1),
        date(2024, 2, 29),
    )


def test_dst_spring_forward_uses_elapsed_seconds_on_the_correct_local_date(
    tmp_path: Path,
) -> None:
    connection, devices, categories = _base(tmp_path)
    _session(
        connection,
        devices[0],
        categories[0],
        sequence=1,
        local_date="2026-03-08",
        start="2026-03-08T06:30:00Z",
        status="completed",
        planned=3600,
        planned_completed=3600,
        segments=(("2026-03-08T06:30:00Z", "2026-03-08T07:30:00Z", 3600, "planned", "none"),),
    )
    connection.commit()
    result = AnalyticsService(connection).calculate(AnalyticsFilters("2026-03-08", "2026-03-08"))
    assert result.total_focus_seconds == 3600
