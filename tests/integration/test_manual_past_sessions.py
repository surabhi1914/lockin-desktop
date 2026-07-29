import csv
import json
import shutil
import sqlite3
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest

from app.analytics.analytics_service import AnalyticsService
from app.analytics.history_service import HistoryFilters, HistoryService
from app.analytics.models import AnalyticsFilters
from app.core.ids import new_uuid4
from app.core.wall_clock import ManualWallClock
from app.dashboard.dashboard_service import DashboardService
from app.database.connection import connect_database
from app.database.migrations import initialize_database
from app.models.manual_session import CreateManualSessionCommand, OverlapKind
from app.models.manual_session_errors import (
    ManualSessionOverlapError,
    ManualSessionPersistenceError,
    ManualSessionValidationError,
)
from app.portability.import_models import ImportMode
from app.portability.portable_import_service import PortableImportService
from app.services.manual_session_service import ManualSessionService
from app.services.portable_sync_service import PortableSyncService
from app.services.portable_verification_service import PortableVerificationService
from app.services.session_integrity_service import verify_session_integrity
from tests.phase3_helpers import isolated_category_service, path_config

NOW = datetime(2026, 7, 29, 23, 0, tzinfo=UTC)
STAMP = "2026-07-29T23:00:00Z"


def _database(
    tmp_path: Path,
) -> tuple[sqlite3.Connection, str, str, str]:
    connection = initialize_database(tmp_path / "lockin.sqlite3")
    device_id = new_uuid4()
    category_id = new_uuid4()
    archived_id = new_uuid4()
    connection.execute(
        "INSERT INTO devices VALUES (?, 'This device', ?, ?)",
        (device_id, STAMP, STAMP),
    )
    for identifier, name, active in (
        (category_id, "Machine Learning", 1),
        (archived_id, "Archived Study", 0),
    ):
        connection.execute(
            "INSERT INTO categories VALUES (?, ?, NULL, ?, ?, ?)",
            (identifier, name, active, STAMP, STAMP),
        )
    connection.commit()
    return connection, device_id, category_id, archived_id


def _service(
    connection: sqlite3.Connection,
    device_id: str,
    **kwargs: object,
) -> ManualSessionService:
    return ManualSessionService(
        connection,
        device_id,
        wall_clock=ManualWallClock(NOW),
        **kwargs,  # type: ignore[arg-type]
    )


def _command(
    category_id: str,
    *,
    day: date = date(2026, 7, 28),
    start: time = time(19),
    actual: int = 90,
    planned: int = 90,
    fold: int | None = None,
    confirmed: bool = False,
) -> CreateManualSessionCommand:
    return CreateManualSessionCommand(
        day,
        start,
        actual,
        planned,
        category_id,
        "America/Detroit",
        fold,
        confirmed,
    )


@pytest.mark.parametrize(
    ("actual", "planned", "status", "planned_focus", "overtime", "stopped"),
    (
        (90, 90, "completed", 5400, 0, 0),
        (80, 60, "completed_with_overtime", 3600, 1200, 0),
        (75, 120, "stopped_early", 4500, 0, 2700),
    ),
)
def test_manual_status_aggregates_segments_and_prohibited_rows(
    tmp_path: Path,
    actual: int,
    planned: int,
    status: str,
    planned_focus: int,
    overtime: int,
    stopped: int,
) -> None:
    connection, device_id, category_id, _archived = _database(tmp_path)
    result = _service(connection, device_id).create_manual_session(
        _command(category_id, actual=actual, planned=planned)
    )
    session = connection.execute("SELECT * FROM sessions").fetchone()
    segments = connection.execute("SELECT * FROM segments ORDER BY segment_sequence").fetchall()
    assert result.summary.status == status
    assert session["entry_source"] == "manual"
    assert session["completion_reason"] == "manual_entry"
    assert session["actual_focus_seconds"] == actual * 60
    assert session["planned_focus_completed_seconds"] == planned_focus
    assert session["overtime_seconds"] == overtime
    assert session["stopped_early_seconds"] == stopped
    assert session["continuous_block_count"] == 1
    assert session["longest_continuous_seconds"] == actual * 60
    assert {row["continuity_group_id"] for row in segments} == {segments[0]["continuity_group_id"]}
    assert [row["focus_phase"] for row in segments] == (
        ["planned", "overtime"] if overtime else ["planned"]
    )
    assert all(row["segment_type"] == "focus" and row["ended_at_utc"] for row in segments)
    prohibited = connection.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM runtime_session_state),
          (SELECT COUNT(*) FROM recovery_events),
          (SELECT COUNT(*) FROM distractions)
        """
    ).fetchone()
    assert tuple(prohibited) == (0, 0, 0)
    assert verify_session_integrity(connection).healthy
    connection.close()


def test_validation_archived_category_and_dst_rules(tmp_path: Path) -> None:
    connection, device_id, category_id, archived_id = _database(tmp_path)
    service = _service(connection, device_id)
    assert service.create_manual_session(_command(archived_id)).summary.category_name == (
        "Archived Study"
    )
    for command, message in (
        (_command(category_id, day=date(2026, 7, 30)), "future"),
        (_command(category_id, actual=0), "1 minute"),
        (_command(category_id, actual=1441), "24 hours"),
        (_command("", actual=30), "Category is required"),
        (_command(category_id, start=time(19, tzinfo=UTC)), "local wall time"),
        (_command(category_id, fold=2), "first or second"),
        (_command("missing"), "no longer exists"),
        (
            _command(category_id, day=date(2026, 3, 8), start=time(2, 30)),
            "does not exist",
        ),
    ):
        with pytest.raises(ManualSessionValidationError, match=message):
            service.create_manual_session(command)
    later_clock = ManualWallClock(datetime(2026, 12, 1, tzinfo=UTC))
    dst_service = ManualSessionService(connection, device_id, wall_clock=later_clock)
    ambiguous = _command(category_id, day=date(2026, 11, 1), start=time(1, 30))
    with pytest.raises(ManualSessionValidationError, match="occurs twice"):
        dst_service.resolve(ambiguous)
    first = dst_service.resolve(
        _command(category_id, day=date(2026, 11, 1), start=time(1, 30), fold=0)
    )
    second = dst_service.resolve(
        _command(category_id, day=date(2026, 11, 1), start=time(1, 30), fold=1)
    )
    difference = second.started_at.astimezone(UTC) - first.started_at.astimezone(UTC)
    assert int(difference.total_seconds()) == 3600
    connection.close()


def test_overlap_duplicate_warning_and_unresolved_block(tmp_path: Path) -> None:
    connection, device_id, category_id, archived_id = _database(tmp_path)
    service = _service(connection, device_id)
    service.create_manual_session(_command(category_id))
    with pytest.raises(ManualSessionOverlapError) as duplicate:
        service.create_manual_session(_command(category_id))
    assert duplicate.value.overlap.kind is OverlapKind.DUPLICATE
    partial = _command(category_id, start=time(19, 30), actual=90)
    with pytest.raises(ManualSessionOverlapError) as warning:
        service.create_manual_session(partial)
    assert warning.value.overlap.kind is OverlapKind.PARTIAL
    assert service.create_manual_session(
        _command(category_id, start=time(19, 30), actual=90, confirmed=True)
    )
    full = _command(archived_id, start=time(19, 45), actual=15)
    with pytest.raises(ManualSessionOverlapError) as strong:
        service.create_manual_session(full)
    assert strong.value.overlap.kind is OverlapKind.FULL
    connection.execute(
        """
        INSERT INTO sessions(
          session_id,schema_version,device_id,session_sequence,category_id,
          category_name_snapshot,local_date_started,timezone_name,
          utc_offset_started_minutes,started_at_utc,started_at_local,
          planned_focus_seconds,status,created_at_utc,updated_at_utc,entry_source
        ) VALUES (?,2,?,99,?,'Machine Learning','2026-07-29','America/Detroit',
                  -240,'2026-07-29T20:00:00Z','2026-07-29T16:00:00-04:00',
                  600,'running',?,?, 'timer')
        """,
        (new_uuid4(), device_id, category_id, STAMP, STAMP),
    )
    connection.commit()
    with pytest.raises(ManualSessionOverlapError) as unresolved:
        service.create_manual_session(
            _command(category_id, start=time(10), actual=10, confirmed=True)
        )
    assert unresolved.value.overlap.kind is OverlapKind.UNRESOLVED
    connection.close()


def test_transaction_rollback_and_sync_failure_are_safe(tmp_path: Path) -> None:
    connection, device_id, category_id, _archived = _database(tmp_path)

    def fail(point: str) -> None:
        if point == "after_session_insert":
            raise RuntimeError("injected")

    with pytest.raises(ManualSessionPersistenceError):
        _service(connection, device_id, failure_injector=fail).create_manual_session(
            _command(category_id)
        )
    assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    result = _service(
        connection,
        device_id,
        post_create_sync=lambda _session_id: (False, "offline"),
    ).create_manual_session(_command(category_id))
    assert not result.portable_synced
    assert result.message == "Past session saved locally; portable sync pending."
    assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    raised = _service(
        connection,
        device_id,
        post_create_sync=lambda _session_id: (_ for _ in ()).throw(OSError("offline")),
    ).create_manual_session(_command(category_id, start=time(17)))
    assert not raised.portable_synced
    assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 2
    connection.close()


def test_cross_midnight_dashboard_analytics_history_and_cache_invalidation(
    tmp_path: Path,
) -> None:
    connection, device_id, category_id, _archived = _database(tmp_path)
    dashboard = DashboardService(
        connection,
        now_provider=lambda: datetime(2026, 7, 29, 12, tzinfo=UTC),
    )
    analytics = AnalyticsService(connection, current_device_id=device_id)
    filters = AnalyticsFilters("2026-07-28", "2026-07-29")
    assert dashboard.snapshot().today_focus_seconds == 0
    assert analytics.calculate(filters).total_focus_seconds == 0
    result = _service(connection, device_id).create_manual_session(
        _command(category_id, start=time(23, 30), actual=60, planned=60)
    )
    assert dashboard.snapshot().today_focus_seconds == 1800
    statistics = analytics.calculate(filters)
    assert statistics.total_focus_seconds == 3600
    assert statistics.longest_block_seconds == 3600
    assert statistics.pause_count == statistics.distraction_count == 0
    manual_only = analytics.calculate(
        AnalyticsFilters("2026-07-28", "2026-07-29", entry_sources=("manual",))
    )
    assert manual_only.session_count == 1
    history = HistoryService(connection)
    rows = history.search(HistoryFilters(entry_sources=("manual",))).rows
    assert len(rows) == 1 and rows[0].entry_source == "manual"
    assert history.detail(result.summary.session_id).session.entry_source == "manual"
    connection.close()


def test_portable_round_trip_preserves_manual_source_and_midnight_parts(
    tmp_path: Path,
) -> None:
    config = path_config(tmp_path)
    categories, connection, _store = isolated_category_service(config)
    device_id = new_uuid4()
    connection.execute(
        "INSERT INTO devices VALUES (?, 'This device', ?, ?)",
        (device_id, STAMP, STAMP),
    )
    connection.commit()
    category = categories.list_active()[0]
    sync = PortableSyncService(
        connection, config.portable_root, config.runtime_root / "portable_backups"
    )
    result = ManualSessionService(
        connection,
        device_id,
        wall_clock=ManualWallClock(NOW),
        post_create_sync=lambda session_id: (
            lambda synced: (synced.success, "synced" if synced.success else "pending")
        )(sync.sync_session(session_id)),
    ).create_manual_session(
        _command(category.category_id, start=time(23, 30), actual=60, planned=60)
    )
    assert result.portable_synced
    segment_rows = sum(
        1
        for path in (config.portable_root / "segments").rglob("*.csv")
        for _line in path.read_text(encoding="utf-8").splitlines()[1:]
    )
    assert segment_rows == 2
    target = tmp_path / "rebuilt"
    imported = PortableImportService().run(config.portable_root, target, mode=ImportMode.FRESH)
    assert imported.success
    rebuilt = connect_database(imported.database_path)
    session = rebuilt.execute(
        "SELECT * FROM sessions WHERE session_id = ?", (result.summary.session_id,)
    ).fetchone()
    assert session["entry_source"] == "manual"
    assert session["manual_entry_created_at_utc"]
    assert rebuilt.execute("SELECT COUNT(*) FROM runtime_session_state").fetchone()[0] == 0
    assert verify_session_integrity(rebuilt).healthy
    rebuilt.close()
    connection.close()


def test_legacy_portable_sessions_import_as_imported_and_upgrade_explicitly(
    tmp_path: Path,
) -> None:
    source = Path(__file__).parents[1] / "fixtures" / "portable_data"
    portable = tmp_path / "legacy portable"
    shutil.copytree(source, portable)
    first = PortableImportService().run(
        portable, tmp_path / "legacy rebuilt", mode=ImportMode.FRESH
    )
    assert first.success
    connection = connect_database(first.database_path)
    session = connection.execute("SELECT * FROM sessions").fetchone()
    assert session["entry_source"] == "imported"
    assert session["manual_entry_created_at_utc"] is None
    sync = PortableSyncService(
        connection, portable, tmp_path / "legacy rebuilt" / "portable_backups"
    )
    assert sync.sync_all().success
    manifest = json.loads((portable / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_schema_version"] == 2
    session_path = next((portable / "sessions").rglob("*.csv"))
    with session_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert "entry_source" in (rows[0] if rows else {})
    assert rows[0]["entry_source"] == "imported"
    assert list((tmp_path / "legacy rebuilt" / "portable_backups" / "sessions").iterdir())
    assert (
        PortableVerificationService(
            connection,
            portable,
            tmp_path / "legacy rebuilt" / "portable_backups",
        )
        .verify()
        .healthy
    )
    connection.close()
    second = PortableImportService().run(
        portable, tmp_path / "schema2 rebuilt", mode=ImportMode.FRESH
    )
    assert second.success
    rebuilt = connect_database(second.database_path)
    assert rebuilt.execute("SELECT entry_source FROM sessions").fetchone()[0] == "imported"
    rebuilt.close()
