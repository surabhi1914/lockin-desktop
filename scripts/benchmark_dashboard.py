"""Build a disposable 10,000-session fixture and benchmark Home aggregation."""

import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.dashboard.dashboard_service import DashboardService
from app.database.migrations import initialize_database


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="lockin-dashboard-benchmark-"))
    connection = initialize_database(root / "lockin.sqlite3")
    device = str(uuid5(NAMESPACE_URL, "lockin-dashboard-device"))
    category = str(uuid5(NAMESPACE_URL, "lockin-dashboard-category"))
    stamp = "2021-01-01T12:00:00Z"
    connection.execute("INSERT INTO devices VALUES (?, 'Benchmark', ?, ?)", (device, stamp, stamp))
    connection.execute(
        "INSERT INTO categories VALUES (?, 'Benchmark', NULL, 1, ?, ?)",
        (category, stamp, stamp),
    )
    sessions: list[tuple[object, ...]] = []
    segments: list[tuple[object, ...]] = []
    origin = datetime(2021, 1, 1, 14, tzinfo=UTC)
    for index in range(10_000):
        start = origin + timedelta(hours=index * 4)
        end = start + timedelta(minutes=50)
        session_id = str(uuid5(NAMESPACE_URL, f"dashboard-session-{index}"))
        segment_id = str(uuid5(NAMESPACE_URL, f"dashboard-segment-{index}"))
        group_id = str(uuid5(NAMESPACE_URL, f"dashboard-group-{index}"))
        started = start.isoformat(timespec="seconds").replace("+00:00", "Z")
        ended = end.isoformat(timespec="seconds").replace("+00:00", "Z")
        sessions.append(
            (
                session_id,
                device,
                index + 1,
                category,
                start.date().isoformat(),
                started,
                ended,
            )
        )
        segments.append((segment_id, session_id, device, started, ended, group_id))
    connection.executemany(
        """
        INSERT INTO sessions(
          session_id,schema_version,device_id,session_sequence,category_id,
          category_name_snapshot,local_date_started,timezone_name,
          utc_offset_started_minutes,started_at_utc,started_at_local,ended_at_utc,
          ended_at_local,planned_focus_seconds,actual_focus_seconds,
          planned_focus_completed_seconds,status,created_at_utc,updated_at_utc
        ) VALUES (?,1,?,?,?,'Benchmark',?,'America/Detroit',-300,?, ?,?, ?,3000,3000,
                  3000,'completed',?,?)
        """,
        [
            (row[0], row[1], row[2], row[3], row[4], row[5], row[5], row[6], row[6], row[5], row[6])
            for row in sessions
        ],
    )
    connection.executemany(
        """
        INSERT INTO segments(
          segment_id,schema_version,session_id,device_id,segment_sequence,segment_type,
          started_at_utc,ended_at_utc,timezone_name,utc_offset_started_minutes,
          duration_seconds,counts_as_focus,pause_classification,breaks_continuity,
          continuity_group_id,pause_grace_threshold_seconds,focus_phase,end_reason,
          created_at_utc,updated_at_utc
        ) VALUES (?,1,?,?,1,'focus',?,?,'America/Detroit',-300,3000,1,'none',0,?,10,
                  'planned','timer_completed',?,?)
        """,
        [(*row, row[3], row[4]) for row in segments],
    )
    connection.commit()
    service = DashboardService(
        connection,
        now_provider=lambda: datetime(2025, 12, 31, 17, tzinfo=UTC),
    )
    started_at = time.perf_counter()
    snapshot = service.snapshot()
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    plan = connection.execute(
        """
        EXPLAIN QUERY PLAN SELECT g.segment_id FROM segments g
        JOIN sessions s ON s.session_id=g.session_id
        WHERE g.counts_as_focus=1 AND g.ended_at_utc IS NOT NULL
          AND s.status IN ('completed','completed_with_overtime','stopped_early','recovered')
        ORDER BY g.started_at_utc, g.segment_id
        """
    ).fetchall()
    connection.close()
    print("Dashboard benchmark: OK")
    print(f"sessions=10000 elapsed_ms={elapsed_ms:.2f} today={snapshot.today_focus_seconds}")
    print("query_plan=" + " | ".join(str(row[3]) for row in plan))
    return 0 if elapsed_ms < 2000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
