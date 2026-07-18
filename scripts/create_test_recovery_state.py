"""Create an isolated developer-only unfinished recovery fixture."""

import argparse
import tempfile
from pathlib import Path

from app.core.ids import new_uuid4
from app.database.migrations import initialize_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a disposable recovery state")
    parser.add_argument("--scenario", choices=("crash-running", "sleep-paused"), required=True)
    parser.add_argument("--runtime-root", type=Path)
    args = parser.parse_args(argv)
    runtime = args.runtime_root or Path(tempfile.mkdtemp(prefix="lockin-recovery-"))
    database = runtime / "lockin.sqlite3"
    connection = initialize_database(database)
    device_id, category_id, session_id, segment_id = (new_uuid4() for _ in range(4))
    stamp = "2026-07-17T16:00:00Z"
    heartbeat = "2026-07-17T16:00:30Z"
    connection.execute(
        "INSERT INTO devices VALUES (?, 'Recovery fixture', ?, ?)",
        (device_id, stamp, stamp),
    )
    connection.execute(
        "INSERT INTO categories VALUES (?, 'Recovery fixture', NULL, 1, ?, ?)",
        (category_id, stamp, stamp),
    )
    state = "running" if args.scenario == "crash-running" else "paused"
    connection.execute(
        """
        INSERT INTO sessions(
            session_id, schema_version, device_id, session_sequence, category_id,
            category_name_snapshot, local_date_started, timezone_name,
            utc_offset_started_minutes, started_at_utc, started_at_local,
            planned_focus_seconds, actual_focus_seconds,
            planned_focus_completed_seconds, total_pause_seconds, wall_clock_seconds,
            status, created_at_utc, updated_at_utc
        ) VALUES (?, 1, ?, 1, ?, 'Recovery fixture', '2026-07-17',
                  'America/Detroit', -240, ?, '2026-07-17T12:00:00-04:00',
                  1500, 30, 30, 0, 30, ?, ?, ?)
        """,
        (session_id, device_id, category_id, stamp, state, stamp, heartbeat),
    )
    if args.scenario == "sleep-paused":
        connection.execute(
            """
            INSERT INTO segments(
                segment_id, schema_version, session_id, device_id, segment_sequence,
                segment_type, started_at_utc, ended_at_utc, timezone_name,
                utc_offset_started_minutes, duration_seconds, counts_as_focus,
                pause_classification, breaks_continuity, continuity_group_id,
                pause_grace_threshold_seconds, focus_phase, end_reason,
                created_at_utc, updated_at_utc
            ) VALUES (?,1,?,?,1,'focus',?,?,'America/Detroit',-240,30,1,
                      'none',0,?,10,'planned','system_sleep',?,?)
            """,
            (segment_id, session_id, device_id, stamp, heartbeat, new_uuid4(), stamp, heartbeat),
        )
        segment_id = new_uuid4()
        connection.execute(
            """
            INSERT INTO segments(
                segment_id, schema_version, session_id, device_id, segment_sequence,
                segment_type, started_at_utc, timezone_name, utc_offset_started_minutes,
                counts_as_focus, pause_classification, breaks_continuity,
                continuity_group_id, pause_grace_threshold_seconds, focus_phase,
                created_at_utc, updated_at_utc
            ) VALUES (?,1,?,?,2,'pause',?,'America/Detroit',-240,0,'system_sleep',1,
                      ?,10,'not_applicable',?,?)
            """,
            (segment_id, session_id, device_id, heartbeat, new_uuid4(), heartbeat, heartbeat),
        )
    else:
        connection.execute(
            """
            INSERT INTO segments(
                segment_id, schema_version, session_id, device_id, segment_sequence,
                segment_type, started_at_utc, timezone_name, utc_offset_started_minutes,
                counts_as_focus, pause_classification, breaks_continuity,
                continuity_group_id, pause_grace_threshold_seconds, focus_phase,
                created_at_utc, updated_at_utc
            ) VALUES (?,1,?,?,1,'focus',?,'America/Detroit',-240,1,'none',0,
                      ?,10,'planned',?,?)
            """,
            (segment_id, session_id, device_id, stamp, new_uuid4(), stamp, heartbeat),
        )
    connection.execute(
        """
        INSERT INTO runtime_session_state(
            session_id, timer_state, temporary_intention_text,
            remaining_planned_seconds, is_overtime, last_heartbeat_at_utc,
            updated_at_utc, timer_version, confirmed_planned_focus_seconds,
            confirmed_overtime_seconds, confirmed_pause_seconds,
            confirmed_wall_clock_seconds, sleep_started_at_utc
        ) VALUES (?, ?, NULL, 1470, 0, ?, ?, 2, 30, 0, 0, 30, ?)
        """,
        (
            session_id,
            state,
            heartbeat,
            heartbeat,
            heartbeat if args.scenario == "sleep-paused" else None,
        ),
    )
    connection.commit()
    connection.close()
    print(f"scenario: {args.scenario}")
    print(f"runtime_root: {runtime.resolve()}")
    print(f"database: {database.resolve()}")
    print(f"session_id: {session_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
