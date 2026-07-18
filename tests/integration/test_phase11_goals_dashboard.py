import csv
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.bootstrap import run_phase0_bootstrap
from app.core.ids import new_uuid4
from app.core.paths import PathConfig
from app.dashboard.dashboard_service import DashboardService
from app.database.migrations import initialize_database
from app.services.daily_goal_service import DailyGoalService


def _goal_service(tmp_path: Path) -> tuple[sqlite3.Connection, DailyGoalService]:
    config = PathConfig(tmp_path, tmp_path, tmp_path / "portable")
    assert run_phase0_bootstrap(config=config).success
    connection = initialize_database(config.database_path)
    service = DailyGoalService(
        connection,
        config.portable_root / "daily_goals.csv",
        tmp_path / "backups",
        today_provider=lambda: date(2026, 7, 17),
        timestamp_provider=lambda: "2026-07-17T12:00:00Z",
    )
    return connection, service


def test_goal_changes_create_history_csv_and_prevent_overlap(tmp_path: Path) -> None:
    connection, service = _goal_service(tmp_path)
    first = service.set_goal(3600, "2026-07-17")
    future = service.set_goal(7200, "2026-07-20")
    goals = service.list_all()
    assert goals[0].goal_id == first.goal_id
    assert goals[0].effective_to_date == "2026-07-19"
    assert goals[1] == future
    updated = service.set_goal(5400, "2026-07-20")
    assert updated.goal_id == future.goal_id and updated.goal_seconds == 5400
    with (tmp_path / "portable" / "daily_goals.csv").open(encoding="utf-8", newline="") as handle:
        assert [row["goal_seconds"] for row in csv.DictReader(handle)] == ["3600", "5400"]
    with pytest.raises(sqlite3.IntegrityError, match="overlap"):
        connection.execute(
            "INSERT INTO daily_goals VALUES (?,?,?,?,?,?)",
            (
                new_uuid4(),
                "2026-07-18",
                "2026-07-21",
                60,
                "2026-07-17T12:00:00Z",
                "2026-07-17T12:00:00Z",
            ),
        )
    with pytest.raises(ValueError, match="today or in the future"):
        service.set_goal(600, "2026-07-16")


def _seed_base(connection: sqlite3.Connection) -> tuple[str, str]:
    device, category = new_uuid4(), new_uuid4()
    stamp = "2026-07-01T12:00:00Z"
    connection.execute(
        "INSERT INTO devices VALUES (?, 'Dashboard fixture', ?, ?)", (device, stamp, stamp)
    )
    connection.execute(
        "INSERT INTO categories VALUES (?, 'Dashboard', NULL, 1, ?, ?)",
        (category, stamp, stamp),
    )
    return device, category


def _seed_focus(
    connection: sqlite3.Connection,
    device: str,
    category: str,
    *,
    start: str,
    end: str,
    duration: int,
    status: str = "completed",
    group: str | None = None,
) -> str:
    session, segment = new_uuid4(), new_uuid4()
    local_date = datetime.fromisoformat(start.replace("Z", "+00:00")).date().isoformat()
    connection.execute(
        """
        INSERT INTO sessions(
            session_id,schema_version,device_id,session_sequence,category_id,
            category_name_snapshot,local_date_started,timezone_name,
            utc_offset_started_minutes,started_at_utc,started_at_local,ended_at_utc,
            ended_at_local,planned_focus_seconds,actual_focus_seconds,
            planned_focus_completed_seconds,status,created_at_utc,updated_at_utc
        ) VALUES (?,1,?,(
                  SELECT COALESCE(MAX(session_sequence),0)+1 FROM sessions WHERE device_id=?
                  ),
                  ?,'Dashboard',?,'America/Detroit',-240,?,?,?,'2026-07-17T12:00:00-04:00',
                  ?,?,?,?, ?,?)
        """,
        (
            session,
            device,
            device,
            category,
            local_date,
            start,
            start.replace("Z", "-04:00"),
            end,
            max(60, duration),
            duration,
            duration,
            status,
            start,
            end,
        ),
    )
    connection.execute(
        """
        INSERT INTO segments(
            segment_id,schema_version,session_id,device_id,segment_sequence,segment_type,
            started_at_utc,ended_at_utc,timezone_name,utc_offset_started_minutes,
            duration_seconds,counts_as_focus,pause_classification,breaks_continuity,
            continuity_group_id,pause_grace_threshold_seconds,focus_phase,end_reason,
            created_at_utc,updated_at_utc
        ) VALUES (?,1,?,?,1,'focus',?,?,'America/Detroit',-240,?,1,'none',0,?,10,
                  'planned','timer_completed',?,?)
        """,
        (segment, session, device, start, end, duration, group or new_uuid4(), start, end),
    )
    return session


def test_dashboard_allocates_local_dates_and_includes_recovered_not_discarded(
    tmp_path: Path,
) -> None:
    connection = initialize_database(tmp_path / "lockin.sqlite3")
    device, category = _seed_base(connection)
    _seed_focus(
        connection,
        device,
        category,
        start="2026-07-17T14:00:00Z",
        end="2026-07-17T15:00:00Z",
        duration=3600,
        group="today-main",
    )
    _seed_focus(
        connection,
        device,
        category,
        start="2026-07-17T15:00:00Z",
        end="2026-07-17T15:30:00Z",
        duration=1800,
        status="recovered",
    )
    _seed_focus(
        connection,
        device,
        category,
        start="2026-07-17T16:00:00Z",
        end="2026-07-17T17:00:00Z",
        duration=3600,
        status="discarded",
    )
    _seed_focus(
        connection,
        device,
        category,
        start="2026-07-16T14:00:00Z",
        end="2026-07-16T14:45:00Z",
        duration=2700,
    )
    _seed_focus(
        connection,
        device,
        category,
        start="2026-07-17T03:30:00Z",
        end="2026-07-17T04:30:00Z",
        duration=3600,
    )
    stamp = "2026-07-16T00:00:00Z"
    connection.execute(
        "INSERT INTO daily_goals VALUES (?, '2026-07-16', NULL, 3600, ?, ?)",
        (new_uuid4(), stamp, stamp),
    )
    connection.commit()
    dashboard = DashboardService(
        connection,
        now_provider=lambda: datetime(2026, 7, 17, 16, 0, tzinfo=UTC),
    )
    result = dashboard.snapshot()
    assert result.today_focus_seconds == 7200
    assert result.yesterday_focus_seconds == 4500
    assert result.today_progress_ratio == 2.0
    assert result.today_longest_block_seconds == 3600
    assert result.personal_longest_block_seconds == 3600
    assert result.goal_streak_days == 2
    assert "reached" in result.motivation_message.casefold()


def test_dashboard_revision_cache_invalidates_after_session_write(tmp_path: Path) -> None:
    connection = initialize_database(tmp_path / "lockin.sqlite3")
    device, category = _seed_base(connection)
    dashboard = DashboardService(
        connection,
        now_provider=lambda: datetime(2026, 7, 17, 16, 0, tzinfo=UTC),
    )
    first = dashboard.snapshot()
    assert first.today_focus_seconds == 0
    _seed_focus(
        connection,
        device,
        category,
        start="2026-07-17T14:00:00Z",
        end="2026-07-17T14:10:00Z",
        duration=600,
    )
    connection.commit()
    second = dashboard.snapshot()
    assert second.today_focus_seconds == 600 and second is not first


@pytest.mark.parametrize(
    ("ratio", "fragment"),
    ((None, "set a daily goal"), (0.8, "close"), (1.0, "reached")),
)
def test_motivation_boundaries_are_deterministic_and_supportive(
    ratio: float | None, fragment: str
) -> None:
    assert fragment in DashboardService._motivation(True, ratio, 0, 0).casefold()
