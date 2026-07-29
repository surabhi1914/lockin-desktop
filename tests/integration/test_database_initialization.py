import sqlite3
from importlib.resources import files
from pathlib import Path

import pytest

from app.core.checksums import record_checksum
from app.core.errors import DatabaseVersionError
from app.core.ids import new_uuid4
from app.database.migrations import current_schema_version, initialize_database
from app.services.session_integrity_service import verify_session_integrity

EXPECTED_TABLES = {
    "schema_migrations",
    "app_metadata",
    "devices",
    "categories",
    "daily_goals",
    "sessions",
    "segments",
    "distractions",
    "runtime_session_state",
    "sync_ledger",
    "recovery_events",
}


def _seed_device_category(connection: sqlite3.Connection) -> tuple[str, str]:
    device_id = new_uuid4()
    category_id = new_uuid4()
    timestamp = "2026-07-16T12:00:00Z"
    connection.execute(
        "INSERT INTO devices VALUES (?, ?, ?, ?)",
        (device_id, "Test", timestamp, timestamp),
    )
    connection.execute(
        "INSERT INTO categories VALUES (?, ?, ?, ?, ?, ?)",
        (category_id, "Research", None, 1, timestamp, timestamp),
    )
    connection.commit()
    return device_id, category_id


def _insert_session(
    connection: sqlite3.Connection, device_id: str, category_id: str, sequence: int = 1
) -> str:
    session_id = new_uuid4()
    connection.execute(
        """
        INSERT INTO sessions (
            session_id, schema_version, device_id, session_sequence, category_id,
            category_name_snapshot, local_date_started, timezone_name,
            utc_offset_started_minutes, started_at_utc, started_at_local,
            planned_focus_seconds, status, created_at_utc, updated_at_utc
        ) VALUES (?, 1, ?, ?, ?, 'Research', '2026-07-16', 'America/Detroit', -240,
                  '2026-07-16T12:00:00Z', '2026-07-16T08:00:00-04:00', 1500,
                  'running', '2026-07-16T12:00:00Z', '2026-07-16T12:00:00Z')
        """,
        (session_id, device_id, sequence, category_id),
    )
    connection.commit()
    return session_id


def test_new_database_initializes_and_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "runtime" / "lockin.sqlite3"
    connection = initialize_database(path)
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert tables >= EXPECTED_TABLES
    assert current_schema_version(connection) == 5
    assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 5
    runtime_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(runtime_session_state)")
    }
    assert "timer_version" in runtime_columns
    assert "confirmed_planned_focus_seconds" in runtime_columns
    assert "sleep_started_at_utc" in runtime_columns
    connection.close()

    second = initialize_database(path)
    assert second.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 5
    assert second.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    second.close()


def test_case_insensitive_category_uniqueness_and_negative_duration(tmp_path: Path) -> None:
    connection = initialize_database(tmp_path / "database.sqlite3")
    _, category_id = _seed_device_category(connection)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO categories VALUES (?, ?, NULL, 1, ?, ?)",
            (
                new_uuid4(),
                "research",
                "2026-07-16T12:00:00Z",
                "2026-07-16T12:00:00Z",
            ),
        )
    assert category_id
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO daily_goals VALUES (?, '2026-01-01', NULL, -1, ?, ?)",
            (new_uuid4(), "2026-07-16T12:00:00Z", "2026-07-16T12:00:00Z"),
        )
    connection.close()


def test_invalid_enum_and_session_sequence_uniqueness(tmp_path: Path) -> None:
    connection = initialize_database(tmp_path / "database.sqlite3")
    device_id, category_id = _seed_device_category(connection)
    _insert_session(connection, device_id, category_id)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_session(connection, device_id, category_id)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO sessions (
              session_id, schema_version, device_id, session_sequence, category_id,
              category_name_snapshot, local_date_started, timezone_name,
              utc_offset_started_minutes, started_at_utc, started_at_local,
              planned_focus_seconds, status, created_at_utc, updated_at_utc
            ) VALUES (?, 1, ?, 2, ?, 'Research', '2026-07-16', 'America/Detroit', -240,
              '2026-07-16T12:00:00Z', '2026-07-16T08:00:00-04:00', 10, 'invalid',
              '2026-07-16T12:00:00Z', '2026-07-16T12:00:00Z')
            """,
            (new_uuid4(), device_id, category_id),
        )
    connection.close()


def test_runtime_intention_and_sync_ledger_privacy_boundary(tmp_path: Path) -> None:
    connection = initialize_database(tmp_path / "database.sqlite3")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(runtime_session_state)")}
    assert "temporary_intention_text" in columns
    assert connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sync_ledger'"
    ).fetchone()
    assert not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='intentions'"
    ).fetchone()
    connection.close()


def test_newer_database_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations("
            "version INTEGER PRIMARY KEY, applied_at_utc TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO schema_migrations VALUES (6, '2026-07-16T12:00:00Z')")
    with pytest.raises(DatabaseVersionError, match="newer"):
        initialize_database(path)


def test_schema_v1_upgrades_to_v5_without_losing_data(tmp_path: Path) -> None:
    path = tmp_path / "v1.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(files("app.database").joinpath("schema_v1.sql").read_text("utf-8"))
        connection.execute("INSERT INTO schema_migrations VALUES (1, '2026-07-16T12:00:00Z')")
        connection.execute("INSERT INTO app_metadata VALUES ('preserved', 'yes')")
    upgraded = initialize_database(path)
    assert current_schema_version(upgraded) == 5
    assert (
        upgraded.execute("SELECT value FROM app_metadata WHERE key = 'preserved'").fetchone()[0]
        == "yes"
    )
    assert "timer_version" in {
        row[1] for row in upgraded.execute("PRAGMA table_info(runtime_session_state)")
    }
    assert upgraded.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='recovery_events'"
    ).fetchone()
    upgraded.close()


def test_schema_v4_session_upgrade_preserves_rows_foreign_keys_and_checksums(
    tmp_path: Path,
) -> None:
    path = tmp_path / "v4.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        for version in range(1, 5):
            connection.executescript(
                files("app.database").joinpath(f"schema_v{version}.sql").read_text("utf-8")
            )
            connection.execute(
                "INSERT INTO schema_migrations VALUES (?, '2026-07-16T12:00:00Z')",
                (version,),
            )
        device_id, category_id = _seed_device_category(connection)
        session_id = _insert_session(connection, device_id, category_id)
        connection.execute(
            """
            UPDATE sessions SET
              ended_at_utc='2026-07-16T12:01:00Z',
              ended_at_local='2026-07-16T08:01:00-04:00',
              actual_focus_seconds=60,
              planned_focus_completed_seconds=60,
              wall_clock_seconds=60,
              continuous_block_count=1,
              longest_continuous_seconds=60,
              average_continuous_seconds=60,
              median_continuous_seconds=60,
              status='completed',
              completion_reason='timer_completed',
              completed_planned_timer=0
            WHERE session_id=?
            """,
            (session_id,),
        )
        connection.execute(
            """
            INSERT INTO segments(
              segment_id,schema_version,session_id,device_id,segment_sequence,
              segment_type,started_at_utc,ended_at_utc,timezone_name,
              utc_offset_started_minutes,duration_seconds,counts_as_focus,
              pause_classification,breaks_continuity,continuity_group_id,
              pause_grace_threshold_seconds,focus_phase,end_reason,
              created_at_utc,updated_at_utc
            ) VALUES (?,1,?,?,1,'focus','2026-07-16T12:00:00Z',
              '2026-07-16T12:01:00Z','America/Detroit',-240,60,1,'none',0,?,
              10,'planned','timer_completed','2026-07-16T12:00:00Z',
              '2026-07-16T12:01:00Z')
            """,
            (new_uuid4(), session_id, device_id, new_uuid4()),
        )
        row = dict(connection.execute("SELECT * FROM sessions").fetchone())
        row.pop("record_checksum")
        for key in (
            "completed_planned_timer",
            "overtime_enabled",
            "fullscreen_used",
            "quotes_enabled",
            "start_ritual_enabled",
        ):
            row[key] = bool(row[key])
        connection.execute(
            "UPDATE sessions SET record_checksum=? WHERE session_id=?",
            (record_checksum(row), session_id),
        )
    upgraded = initialize_database(path)
    session = upgraded.execute("SELECT * FROM sessions").fetchone()
    assert session["entry_source"] == "timer"
    assert session["manual_entry_created_at_utc"] is None
    assert upgraded.execute("PRAGMA foreign_key_check").fetchall() == []
    assert verify_session_integrity(upgraded).healthy
    upgraded.close()


def test_schema_v5_foreign_key_failure_rolls_back_the_entire_migration(
    tmp_path: Path,
) -> None:
    path = tmp_path / "corrupt-v4.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        for version in range(1, 5):
            connection.executescript(
                files("app.database").joinpath(f"schema_v{version}.sql").read_text("utf-8")
            )
            connection.execute(
                "INSERT INTO schema_migrations VALUES (?, '2026-07-16T12:00:00Z')",
                (version,),
            )
        connection.execute(
            """
            INSERT INTO segments(
              segment_id,schema_version,session_id,device_id,segment_sequence,
              segment_type,started_at_utc,timezone_name,utc_offset_started_minutes,
              duration_seconds,counts_as_focus,pause_classification,
              breaks_continuity,pause_grace_threshold_seconds,focus_phase,
              created_at_utc,updated_at_utc
            ) VALUES (?,1,?,?,1,'focus','2026-07-16T12:00:00Z',
              'America/Detroit',-240,60,1,'none',0,10,'planned',
              '2026-07-16T12:00:00Z','2026-07-16T12:00:00Z')
            """,
            (new_uuid4(), new_uuid4(), new_uuid4()),
        )
        connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="foreign-key violations"):
        initialize_database(path)

    with sqlite3.connect(path) as connection:
        assert current_schema_version(connection) == 4
        assert "entry_source" not in {
            row[1] for row in connection.execute("PRAGMA table_info(sessions)")
        }
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sessions_v5'"
            ).fetchone()
            is None
        )
