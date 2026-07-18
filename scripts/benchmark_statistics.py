"""Benchmark 10k sessions, 50k segments, and 20k distractions over five years."""

import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.analytics.analytics_service import AnalyticsService
from app.analytics.history_service import HistoryFilters, HistoryService
from app.analytics.models import AnalyticsFilters
from app.database.migrations import initialize_database


def _id(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, label))


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="lockin-statistics-benchmark-"))
    connection = initialize_database(root / "lockin.sqlite3")
    stamp = "2021-01-01T00:00:00Z"
    devices = tuple(_id(f"stats-device-{index}") for index in range(5))
    categories = tuple(_id(f"stats-category-{index}") for index in range(10))
    connection.executemany(
        "INSERT INTO devices VALUES (?, ?, ?, ?)",
        [(item, f"Device {index + 1}", stamp, stamp) for index, item in enumerate(devices)],
    )
    connection.executemany(
        "INSERT INTO categories VALUES (?, ?, NULL, 1, ?, ?)",
        [(item, f"Category {index + 1}", stamp, stamp) for index, item in enumerate(categories)],
    )
    sessions: list[tuple[object, ...]] = []
    segments: list[tuple[object, ...]] = []
    distractions: list[tuple[object, ...]] = []
    origin = datetime(2021, 1, 1, 14, tzinfo=UTC)
    statuses = ("completed", "completed_with_overtime", "stopped_early", "recovered")
    for index in range(10_000):
        start = origin + timedelta(days=index % 1826, minutes=index % 360)
        device = devices[index % len(devices)]
        category = categories[index % len(categories)]
        session_id = _id(f"stats-session-{index}")
        status = statuses[index % len(statuses)]
        start_text = start.isoformat(timespec="seconds").replace("+00:00", "Z")
        end_text = (
            (start + timedelta(minutes=52)).isoformat(timespec="seconds").replace("+00:00", "Z")
        )
        sessions.append(
            (
                session_id,
                device,
                index + 1,
                category,
                f"Category {index % len(categories) + 1}",
                start.date().isoformat(),
                start_text,
                start_text,
                end_text,
                end_text,
                2400,
                3000,
                2400,
                600,
                120,
                3120,
                2,
                0,
                2,
                2,
                status,
                0,
                1,
                start_text,
                end_text,
            )
        )
        cursor = start
        definitions = (
            ("focus", "planned", "none", 1200),
            ("pause", "not_applicable", "continuity_break", 60),
            ("focus", "planned", "none", 1200),
            ("pause", "not_applicable", "system_sleep", 60),
            ("focus", "overtime", "none", 600),
        )
        group = _id(f"stats-group-{index}")
        segment_ids: list[str] = []
        for sequence, (kind, phase, classification, duration) in enumerate(definitions, start=1):
            segment_id = _id(f"stats-segment-{index}-{sequence}")
            segment_ids.append(segment_id)
            segment_start = cursor
            cursor += timedelta(seconds=duration)
            segment_end = cursor
            started = segment_start.isoformat(timespec="seconds").replace("+00:00", "Z")
            ended = segment_end.isoformat(timespec="seconds").replace("+00:00", "Z")
            focus = kind == "focus"
            segments.append(
                (
                    segment_id,
                    session_id,
                    device,
                    sequence,
                    kind,
                    started,
                    ended,
                    duration,
                    int(focus),
                    classification,
                    int(classification in {"continuity_break", "system_sleep"}),
                    group,
                    phase,
                    started,
                    ended,
                )
            )
        for marker in range(2):
            distractions.append(
                (
                    _id(f"stats-distraction-{index}-{marker}"),
                    session_id,
                    segment_ids[0],
                    device,
                    start_text,
                    start_text,
                    start.date().isoformat(),
                    category,
                    f"Category {index % len(categories) + 1}",
                    marker * 300,
                    2400 - marker * 300,
                    start_text,
                )
            )
    session_columns = (
        "session_id",
        "schema_version",
        "device_id",
        "session_sequence",
        "category_id",
        "category_name_snapshot",
        "local_date_started",
        "timezone_name",
        "utc_offset_started_minutes",
        "started_at_utc",
        "started_at_local",
        "ended_at_utc",
        "ended_at_local",
        "planned_focus_seconds",
        "actual_focus_seconds",
        "planned_focus_completed_seconds",
        "overtime_seconds",
        "total_pause_seconds",
        "wall_clock_seconds",
        "pause_count",
        "short_pause_count",
        "long_pause_count",
        "distraction_count",
        "status",
        "completion_reason",
        "stopped_early_seconds",
        "completed_planned_timer",
        "created_at_utc",
        "updated_at_utc",
        "record_checksum",
    )
    session_values = [
        (
            row[0],
            1,
            *row[1:6],
            "America/Detroit",
            -300,
            *row[6:21],
            "timer_completed",
            *row[21:25],
            "benchmark",
        )
        for row in sessions
    ]
    connection.executemany(
        f"INSERT INTO sessions ({', '.join(session_columns)}) "
        f"VALUES ({', '.join('?' for _ in session_columns)})",
        session_values,
    )
    segment_columns = (
        "segment_id",
        "schema_version",
        "session_id",
        "device_id",
        "segment_sequence",
        "segment_type",
        "started_at_utc",
        "ended_at_utc",
        "timezone_name",
        "utc_offset_started_minutes",
        "duration_seconds",
        "counts_as_focus",
        "pause_classification",
        "breaks_continuity",
        "continuity_group_id",
        "pause_grace_threshold_seconds",
        "focus_phase",
        "end_reason",
        "created_at_utc",
        "updated_at_utc",
    )
    segment_values = [
        (
            row[0],
            1,
            *row[1:7],
            "America/Detroit",
            -300,
            *row[7:12],
            10,
            row[12],
            "benchmark",
            *row[13:15],
        )
        for row in segments
    ]
    connection.executemany(
        f"INSERT INTO segments ({', '.join(segment_columns)}) "
        f"VALUES ({', '.join('?' for _ in segment_columns)})",
        segment_values,
    )
    distraction_columns = (
        "distraction_id",
        "schema_version",
        "session_id",
        "segment_id",
        "device_id",
        "marked_at_utc",
        "marked_at_local",
        "local_date",
        "timezone_name",
        "category_id",
        "category_name_snapshot",
        "elapsed_focus_seconds",
        "remaining_planned_seconds",
        "is_overtime",
        "optional_note",
        "created_at_utc",
    )
    distraction_values = [
        (row[0], 1, *row[1:7], "America/Detroit", *row[7:11], 0, None, row[11])
        for row in distractions
    ]
    connection.executemany(
        f"INSERT INTO distractions ({', '.join(distraction_columns)}) "
        f"VALUES ({', '.join('?' for _ in distraction_columns)})",
        distraction_values,
    )
    connection.commit()
    filters = AnalyticsFilters("2021-01-01", "2025-12-31")
    service = AnalyticsService(connection, current_device_id=devices[0])
    performance_started = time.perf_counter()
    result = service.calculate(filters)
    analytics_ms = (time.perf_counter() - performance_started) * 1000
    performance_started = time.perf_counter()
    history = HistoryService(connection).search(HistoryFilters(page_size=50))
    history_ms = (time.perf_counter() - performance_started) * 1000
    plans = connection.execute(
        """
        EXPLAIN QUERY PLAN SELECT s.session_id FROM sessions s
        WHERE s.status IN ('completed','completed_with_overtime','stopped_early','recovered')
          AND s.local_date_started BETWEEN '2021-01-01' AND '2025-12-31'
        """
    ).fetchall()
    connection.close()
    print("Statistics benchmark: OK")
    print(
        f"sessions=10000 segments=50000 distractions=20000 years=5 "
        f"analytics_ms={analytics_ms:.2f} history_ms={history_ms:.2f} "
        f"focus={result.total_focus_seconds} history_total={history.total_count}"
    )
    print("query_plan=" + " | ".join(str(row[3]) for row in plans))
    return 0 if analytics_ms < 5000 and history_ms < 1000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
