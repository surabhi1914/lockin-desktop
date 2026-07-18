import csv
import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QSettings

from app.core.wall_clock import ManualWallClock
from app.database.connection import connect_database
from app.models.category import Category
from app.models.focus_session_draft import FocusSessionDraft
from app.models.persisted_session import PersistedSession
from app.portability.csv_mapping import portable_row_checksum
from app.portability.database_portable_comparator import compare_database_to_portable
from app.portability.import_models import ImportMode
from app.portability.import_validator import PortableImportValidator, _session_from_csv
from app.portability.portable_import_service import PortableImportService
from app.services.new_device_setup_service import NewDeviceSetupService
from app.services.portable_sync_service import PortableSyncService
from app.services.session_checksum_service import session_checksum
from app.services.session_persistence_service import SessionPersistenceService
from app.timer import ManualClock, TimerConfig, TimerEngine

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _portable_copy(tmp_path: Path) -> Path:
    target = tmp_path / "portable"
    shutil.copytree(PROJECT_ROOT / "portable_data", target)
    return target


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_fresh_rebuild_preserves_history_adds_device_ledger_and_metadata(tmp_path: Path) -> None:
    portable = _portable_copy(tmp_path)
    runtime = tmp_path / "runtime with spaces"
    before = _tree_hashes(portable)
    result = PortableImportService().run(portable, runtime, mode=ImportMode.FRESH)
    assert result.success and result.database_path is not None
    assert result.local_device_id is not None
    assert _tree_hashes(portable) == before
    connection = connect_database(result.database_path)
    historical = {
        row[0]
        for row in connection.execute(
            "SELECT record_id FROM sync_ledger WHERE record_type='device'"
        )
    }
    assert result.local_device_id not in historical
    assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] >= 1
    assert connection.execute("SELECT COUNT(*) FROM segments").fetchone()[0] >= 1
    assert (
        connection.execute("SELECT COUNT(*) FROM sync_ledger").fetchone()[0] == result.inserted - 10
    )
    metadata = connection.execute(
        "SELECT value FROM app_metadata WHERE key = ?", (f"portable_import/{result.import_id}",)
    ).fetchone()[0]
    assert json.loads(metadata)["current_local_device_id"] == result.local_device_id
    assert connection.execute("SELECT COUNT(*) FROM runtime_session_state").fetchone()[0] == 0
    connection.close()
    comparison = compare_database_to_portable(result.database_path, portable)
    assert comparison.healthy and comparison.missing_in_database == 0
    assert comparison.missing_in_portable == 1


def test_merge_reimport_skips_every_exact_record_and_creates_backup(tmp_path: Path) -> None:
    portable = _portable_copy(tmp_path)
    runtime = tmp_path / "runtime"
    first = PortableImportService().run(portable, runtime, mode=ImportMode.FRESH)
    before = first.database_path.read_bytes()
    connection = connect_database(first.database_path)
    device_count = connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    connection.close()
    second = PortableImportService().run(
        portable,
        runtime,
        mode=ImportMode.MERGE,
    )
    assert second.success and second.inserted == 0
    assert second.skipped == first.inserted
    assert second.local_device_id == first.local_device_id
    connection = connect_database(first.database_path)
    assert connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0] == device_count
    connection.close()
    assert second.backup_path is not None and second.backup_path.exists()
    assert second.backup_path.with_suffix(".json").exists()
    assert first.database_path.read_bytes() != before  # import metadata changes only
    assert compare_database_to_portable(first.database_path, portable).healthy


def test_merge_recovers_current_device_from_metadata_when_candidates_are_ambiguous(
    tmp_path: Path,
) -> None:
    portable = _portable_copy(tmp_path)
    runtime = tmp_path / "runtime"
    first = PortableImportService().run(portable, runtime, mode=ImportMode.FRESH)
    extra_device = "22222222-3333-4444-8555-666666666666"
    connection = connect_database(first.database_path)
    connection.execute(
        "INSERT INTO devices VALUES (?, 'Old local install', ?, ?)",
        (extra_device, "2026-07-17T12:00:00Z", "2026-07-17T12:00:00Z"),
    )
    connection.commit()
    connection.close()

    merged = PortableImportService().run(portable, runtime, mode=ImportMode.MERGE)
    assert merged.success
    assert merged.local_device_id == first.local_device_id


def test_merge_restores_missing_history_without_losing_local_rows(tmp_path: Path) -> None:
    portable = _portable_copy(tmp_path)
    runtime = tmp_path / "runtime"
    first = PortableImportService().run(portable, runtime, mode=ImportMode.FRESH)
    connection = connect_database(first.database_path)
    session_id = connection.execute("SELECT session_id FROM distractions LIMIT 1").fetchone()[0]
    segment_count = connection.execute(
        "SELECT COUNT(*) FROM segments WHERE session_id = ?", (session_id,)
    ).fetchone()[0]
    distraction_count = connection.execute(
        "SELECT COUNT(*) FROM distractions WHERE session_id = ?", (session_id,)
    ).fetchone()[0]
    connection.execute("DELETE FROM distractions WHERE session_id = ?", (session_id,))
    connection.execute("DELETE FROM segments WHERE session_id = ?", (session_id,))
    connection.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    connection.execute("INSERT INTO app_metadata(key,value) VALUES ('local-only-test','preserved')")
    connection.commit()
    connection.close()
    merged = PortableImportService().run(
        portable,
        runtime,
        mode=ImportMode.MERGE,
        local_device_id=first.local_device_id,
    )
    assert merged.success and merged.inserted == 1 + segment_count + distraction_count
    connection = connect_database(first.database_path)
    assert (
        connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        == 1
    )
    assert (
        connection.execute(
            "SELECT COUNT(*) FROM segments WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        == segment_count
    )
    assert (
        connection.execute(
            "SELECT COUNT(*) FROM distractions WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        == distraction_count
    )
    assert (
        connection.execute("SELECT value FROM app_metadata WHERE key='local-only-test'").fetchone()[
            0
        ]
        == "preserved"
    )
    connection.close()


def test_same_id_conflict_aborts_and_explicit_skip_preserves_live_content(tmp_path: Path) -> None:
    portable = _portable_copy(tmp_path)
    runtime = tmp_path / "runtime"
    first = PortableImportService().run(portable, runtime, mode=ImportMode.FRESH)
    session_path = next((portable / "sessions").rglob("*.csv"))
    with session_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or ())
    original_name = rows[0]["category_name_snapshot"]
    rows[0]["category_name_snapshot"] = original_name + " source changed"
    rows[0]["record_checksum"] = session_checksum(_session_from_csv(rows[0]))
    with session_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    connection = connect_database(first.database_path)
    session = PersistedSession.from_row(
        connection.execute("SELECT * FROM sessions LIMIT 1").fetchone()
    )
    connection.close()
    before = hashlib.sha256(first.database_path.read_bytes()).hexdigest()
    aborted = PortableImportService().run(portable, runtime, mode=ImportMode.MERGE)
    assert not aborted.success and aborted.conflicts
    assert aborted.conflict_report_path is not None and aborted.conflict_report_path.exists()
    assert "intention" not in aborted.conflict_report_path.read_text(encoding="utf-8").casefold()
    assert hashlib.sha256(first.database_path.read_bytes()).hexdigest() == before
    skipped = PortableImportService().run(
        portable,
        runtime,
        mode=ImportMode.MERGE,
        skip_conflicts=True,
        local_device_id=first.local_device_id,
    )
    assert skipped.success and skipped.conflicts
    connection = connect_database(first.database_path)
    assert (
        connection.execute(
            "SELECT category_name_snapshot FROM sessions WHERE session_id=?", (session.session_id,)
        ).fetchone()[0]
        == original_name
    )
    connection.close()


def test_staging_failure_and_active_session_leave_live_database_usable(tmp_path: Path) -> None:
    portable = _portable_copy(tmp_path)
    portable_hashes = _tree_hashes(portable)
    runtime = tmp_path / "runtime"
    first = PortableImportService().run(portable, runtime, mode=ImportMode.FRESH)
    before = hashlib.sha256(first.database_path.read_bytes()).hexdigest()

    def fail(point: str) -> None:
        if point == "before_replace":
            raise RuntimeError("injected staging failure")

    failed = PortableImportService().run(
        portable,
        runtime,
        mode=ImportMode.MERGE,
        local_device_id=first.local_device_id,
        failure_injector=fail,
    )
    assert not failed.success and failed.staging_path is not None
    assert failed.staging_path.exists()
    assert hashlib.sha256(first.database_path.read_bytes()).hexdigest() == before
    assert _tree_hashes(portable) == portable_hashes
    assert list((runtime / "database_backups").glob("*.sqlite3"))
    with sqlite3.connect(first.database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        session_id, original_status = connection.execute(
            "SELECT session_id, status FROM sessions LIMIT 1"
        ).fetchone()
        connection.execute("UPDATE sessions SET status='running' WHERE session_id=?", (session_id,))
    blocked = PortableImportService().run(portable, runtime, mode=ImportMode.MERGE)
    assert not blocked.success
    assert "active or unfinished" in blocked.errors[0]
    with sqlite3.connect(first.database_path) as connection:
        connection.execute(
            "UPDATE sessions SET status=? WHERE session_id=?", (original_status, session_id)
        )
        connection.execute(
            """
            INSERT INTO runtime_session_state(
                session_id, timer_state, temporary_intention_text,
                remaining_planned_seconds, is_overtime, last_heartbeat_at_utc,
                updated_at_utc, timer_version
            ) VALUES (?, 'running', NULL, 10, 0, NULL, '2026-07-17T12:00:00Z', 1)
            """,
            (session_id,),
        )
    unfinished = PortableImportService().run(portable, runtime, mode=ImportMode.MERGE)
    assert not unfinished.success
    assert "active or unfinished" in unfinished.errors[0]


def test_source_change_during_staging_aborts_before_live_replacement(tmp_path: Path) -> None:
    portable = _portable_copy(tmp_path)
    runtime = tmp_path / "runtime"
    first = PortableImportService().run(portable, runtime, mode=ImportMode.FRESH)
    live_hash = hashlib.sha256(first.database_path.read_bytes()).hexdigest()

    def change_source(point: str) -> None:
        if point == "before_source_guard":
            manifest = portable / "manifest.json"
            manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    failed = PortableImportService().run(
        portable,
        runtime,
        mode=ImportMode.MERGE,
        failure_injector=change_source,
    )
    assert not failed.success
    assert "portable files changed during import" in failed.errors[0]
    assert hashlib.sha256(first.database_path.read_bytes()).hexdigest() == live_hash
    assert failed.backup_path is None


def test_new_device_setup_reuses_valid_setting_and_phase7_exports_only_new_device(
    tmp_path: Path,
) -> None:
    portable = _portable_copy(tmp_path)
    runtime = tmp_path / "runtime"
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    requested = "11111111-2222-4333-8444-555555555555"
    settings.setValue("runtime/device_id", requested)
    setup = NewDeviceSetupService(settings)
    assert setup.verify(portable, runtime).safe
    result = setup.rebuild(portable, runtime)
    assert result.success and result.local_device_id == requested
    before_sessions = sum(
        1 for path in (portable / "sessions").rglob("*.csv") for _ in csv_rows(path)
    )
    connection = connect_database(result.database_path)
    category_row = connection.execute(
        "SELECT * FROM categories ORDER BY category_name LIMIT 1"
    ).fetchone()
    category = Category(
        category_row["category_id"],
        category_row["category_name"],
        category_row["category_icon"],
        bool(category_row["is_active"]),
        category_row["created_at_utc"],
        category_row["updated_at_utc"],
    )
    wall = ManualWallClock(datetime(2026, 7, 18, 16, 0, tzinfo=UTC))
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(60, 10, True), clock)
    persistence = SessionPersistenceService(
        connection, requested, wall_clock=wall, timezone_name="America/Detroit"
    )
    draft = FocusSessionDraft(
        60,
        category.category_id,
        category.category_name,
        "temporary only",
        False,
        True,
        False,
        True,
        False,
        10,
    )
    context = persistence.start_session(draft, category, engine.start())
    clock.advance_seconds(5)
    wall.advance(seconds=5)
    persistence.finalize(engine.stop(), "manual_stop")
    service = PortableSyncService(connection, portable, runtime / "portable_backups")
    synced = service.sync_session(context.session_id)
    repeated = service.sync_session(context.session_id)
    connection.close()
    assert synced.success and synced.counts.devices == 1
    assert synced.counts.sessions == 1 and synced.counts.segments == 1
    assert repeated.success and repeated.counts.sessions == 0
    after_sessions = sum(
        1 for path in (portable / "sessions").rglob("*.csv") for _ in csv_rows(path)
    )
    assert after_sessions == before_sessions + 1


def test_midnight_parts_import_as_one_segment_and_phase7_reexports_valid_parts(
    tmp_path: Path,
) -> None:
    portable = _portable_copy(tmp_path)
    segment_path = next((portable / "segments").rglob("*.csv"))
    with segment_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or ())
    base = rows[-1]
    source = base["source_segment_id"]
    parts: list[dict[str, str]] = []
    for number, utc_start, utc_end, local_start, local_end, local_date in (
        (
            1,
            "2026-07-18T03:59:59Z",
            "2026-07-18T04:00:00Z",
            "2026-07-17T23:59:59-04:00",
            "2026-07-18T00:00:00-04:00",
            "2026-07-17",
        ),
        (
            2,
            "2026-07-18T04:00:00Z",
            "2026-07-18T04:00:01Z",
            "2026-07-18T00:00:00-04:00",
            "2026-07-18T00:00:01-04:00",
            "2026-07-18",
        ),
    ):
        part = {
            **base,
            "segment_id": str(uuid4()),
            "midnight_part_number": str(number),
            "started_at_utc": utc_start,
            "ended_at_utc": utc_end,
            "started_at_local": local_start,
            "ended_at_local": local_end,
            "local_date": local_date,
            "duration_seconds": "1",
            "pause_duration_seconds": "1",
            "crossed_midnight": "true",
        }
        part["record_checksum"] = portable_row_checksum(part)
        parts.append(part)
    with segment_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows([*rows[:-1], *parts])

    runtime = tmp_path / "runtime"
    imported = PortableImportService().run(portable, runtime, mode=ImportMode.FRESH)
    assert imported.success, imported.errors
    connection = connect_database(imported.database_path)
    rebuilt = connection.execute(
        "SELECT duration_seconds FROM segments WHERE segment_id = ?", (source,)
    ).fetchone()
    assert rebuilt is not None and rebuilt[0] == 2

    reexport = tmp_path / "reexport"
    shutil.copytree(portable, reexport)
    for directory in ("sessions", "segments", "distractions"):
        for path in (reexport / directory).rglob("*.csv"):
            header = path.read_text(encoding="utf-8").splitlines()[0]
            path.write_text(header + "\n", encoding="utf-8")
    connection.execute("DELETE FROM sync_ledger")
    connection.commit()
    synced = PortableSyncService(connection, reexport, runtime / "reexport_backups").sync_all()
    connection.close()
    assert synced.success
    report, bundle = PortableImportValidator().validate(reexport)
    assert report.safe and bundle is not None
    exported_parts = [
        row for row in bundle.rows["segments"] if row.values["source_segment_id"] == source
    ]
    assert len(exported_parts) == 2
    assert sum(int(row.values["duration_seconds"]) for row in exported_parts) == 2


def csv_rows(path: Path):
    import csv

    with path.open(encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)
