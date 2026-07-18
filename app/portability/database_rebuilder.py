"""Staging-only SQLite import, verified backups, and atomic promotion."""

import hashlib
import json
import os
import sqlite3
from collections.abc import Callable
from pathlib import Path

from app.core.constants import DATABASE_SCHEMA_VERSION
from app.core.ids import canonicalize_uuid, new_uuid4
from app.core.time_utils import format_utc, utc_now
from app.database.migrations import current_schema_version, initialize_database
from app.portability.import_errors import (
    ActiveSessionBlocksImportError,
    DatabaseRebuildError,
    DatabaseReplacementError,
    ImportBackupError,
    ImportIntegrityError,
)
from app.portability.import_manifest_service import store_import_metadata
from app.portability.import_mapping import (
    category_values,
    device_values,
    distraction_values,
    goal_values,
    segment_values,
    session_values,
)
from app.portability.import_models import ImportMode, ImportPlan, PortableImportBundle
from app.portability.sync_ledger_rebuilder import SyncLedgerRebuilder
from app.services.session_integrity_service import verify_session_integrity

FailureInjector = Callable[[str], None]
SourceGuard = Callable[[], None]


class DatabaseRebuilder:
    def __init__(
        self,
        runtime_root: Path,
        *,
        uuid_provider: Callable[[], str] = new_uuid4,
        failure_injector: FailureInjector | None = None,
        source_guard: SourceGuard | None = None,
    ) -> None:
        self._runtime_root = runtime_root
        self._uuid = uuid_provider
        self._inject = failure_injector or (lambda _point: None)
        self._source_guard = source_guard or (lambda: None)

    def promote(
        self,
        bundle: PortableImportBundle,
        plan: ImportPlan,
        target: Path,
        *,
        import_id: str,
        mode: ImportMode,
        skip_conflicts: bool,
        local_device_id: str | None,
        local_device_label: str,
        allow_replace: bool,
    ) -> tuple[int, int, str, Path | None, Path]:
        started = format_utc(utc_now())
        target = target.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        if mode == ImportMode.FRESH and target.exists() and not allow_replace:
            raise DatabaseRebuildError(
                "fresh rebuild will not overwrite an existing database without permission: "
                f"{target}"
            )
        if mode == ImportMode.MERGE:
            if not target.is_file():
                raise DatabaseRebuildError(f"merge database does not exist: {target}")
            self._assert_merge_allowed(target)
        staging = target.with_name(f".{target.stem}.import-{import_id}.sqlite3")
        if staging.exists():
            raise DatabaseRebuildError(f"staging path already exists: {staging}")
        backup: Path | None = None
        try:
            if mode == ImportMode.MERGE:
                self._sqlite_copy(target, staging)
                connection = initialize_database(staging)
            else:
                connection = initialize_database(staging)
            try:
                self._inject("after_staging_created")
                inserted, skipped, ledger_exclusions = self._apply(
                    connection, bundle, plan, skip_conflicts=skip_conflicts
                )
                device_id = self._ensure_local_device(
                    connection, bundle, local_device_id, local_device_label
                )
                SyncLedgerRebuilder().rebuild(connection, bundle, excluded=ledger_exclusions)
                completed = format_utc(utc_now())
                store_import_metadata(
                    connection,
                    import_id,
                    {
                        "import_id": import_id,
                        "started_at_utc": started,
                        "completed_at_utc": completed,
                        "portable_root": str(bundle.root),
                        "manifest_schema_version": bundle.manifest.manifest_schema_version,
                        "data_schema_version": bundle.manifest.data_schema_version,
                        "mode": mode.value,
                        "inserted": inserted,
                        "skipped": skipped,
                        "conflicts": len(plan.conflicts),
                        "result": "success",
                        "current_local_device_id": device_id,
                    },
                )
                connection.execute(
                    "INSERT OR REPLACE INTO app_metadata(key, value) VALUES (?, ?)",
                    ("portable_quote_source", str(bundle.root / "quotes.csv")),
                )
                connection.commit()
                self._inject("before_integrity")
                self._verify_database(connection)
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                connection.execute("PRAGMA journal_mode = DELETE")
            finally:
                connection.close()
            self._inject("before_source_guard")
            self._source_guard()
            self._inject("before_backup")
            if target.exists():
                backup = self._create_backup(target, reason=f"phase8_{mode.value}_{import_id}")
            self._inject("before_replace")
            try:
                os.replace(staging, target)
            except OSError as exc:
                raise DatabaseReplacementError(
                    f"could not atomically replace database; it may be locked: {target}: {exc}"
                ) from exc
            self._inject("after_replace")
            return inserted, skipped, device_id, backup, staging
        except Exception:
            # Staging is deliberately retained for local diagnostics.
            raise

    def _apply(
        self,
        connection: sqlite3.Connection,
        bundle: PortableImportBundle,
        plan: ImportPlan,
        *,
        skip_conflicts: bool,
    ) -> tuple[int, int, set[tuple[str, str]]]:
        actions = {(item.entity, item.record_id): item.action for item in plan.operations}
        conflicted = {
            (item.entity, item.record_id) for item in plan.operations if item.action == "conflict"
        }
        blocked_sessions = {record_id for entity, record_id in conflicted if entity == "sessions"}
        blocked_segments = {record_id for entity, record_id in conflicted if entity == "segments"}
        blocked_devices = {record_id for entity, record_id in conflicted if entity == "devices"}
        blocked_categories = {
            record_id for entity, record_id in conflicted if entity == "categories"
        }
        excluded: set[tuple[str, str]] = {
            (entity, record_id)
            for entity, record_id in conflicted
            if entity in {"devices", "sessions", "segments", "distractions"}
        }
        inserted = skipped = 0
        connection.execute("BEGIN IMMEDIATE")
        try:
            for entity, table, rows, mapper in (
                ("devices", "devices", bundle.rows["devices"], device_values),
                ("categories", "categories", bundle.rows["categories"], category_values),
                ("daily_goals", "daily_goals", bundle.rows["daily_goals"], goal_values),
                ("sessions", "sessions", bundle.rows["sessions"], session_values),
            ):
                for row in rows:
                    action = actions[(entity, row.record_id)]
                    if entity == "sessions" and (
                        row.values["device_id"] in blocked_devices
                        or row.values["category_id"] in blocked_categories
                    ):
                        blocked_sessions.add(row.record_id)
                        excluded.add(("sessions", row.record_id))
                        skipped += 1
                        continue
                    if action == "insert":
                        self._insert(connection, table, mapper(row))
                        inserted += 1
                    elif action == "skip_exact" or (action == "conflict" and skip_conflicts):
                        skipped += 1
                    else:
                        raise DatabaseRebuildError(
                            f"unresolved conflict prevents staging import: {entity} {row.record_id}"
                        )
            for segment in bundle.logical_segments:
                action = actions[("segments", segment.segment_id)]
                if segment.session_id in blocked_sessions:
                    excluded.update(("segments", row.record_id) for row in segment.portable_rows)
                    skipped += 1
                elif action == "insert":
                    self._insert(connection, "segments", segment_values(segment))
                    inserted += 1
                elif action == "skip_exact" or (action == "conflict" and skip_conflicts):
                    skipped += 1
                else:
                    raise DatabaseRebuildError(f"unresolved segment conflict: {segment.segment_id}")
            for row in bundle.rows["distractions"]:
                action = actions[("distractions", row.record_id)]
                logical_segment = bundle.segment_id_map.get(row.values["segment_id"], "")
                if (
                    row.values["session_id"] in blocked_sessions
                    or logical_segment in blocked_segments
                ):
                    excluded.add(("distractions", row.record_id))
                    skipped += 1
                elif action == "insert":
                    self._insert(connection, "distractions", distraction_values(row, bundle))
                    inserted += 1
                elif action == "skip_exact" or (action == "conflict" and skip_conflicts):
                    skipped += 1
                else:
                    raise DatabaseRebuildError(f"unresolved distraction conflict: {row.record_id}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return inserted, skipped, excluded

    def _ensure_local_device(
        self,
        connection: sqlite3.Connection,
        bundle: PortableImportBundle,
        requested: str | None,
        label: str,
    ) -> str:
        historical = {row.record_id for row in bundle.rows["devices"]}
        if requested is not None:
            try:
                device_id = canonicalize_uuid(requested)
            except ValueError as exc:
                raise DatabaseRebuildError(f"local device ID is invalid: {exc}") from exc
        else:
            existing = self._existing_local_device(connection, historical)
            device_id = existing or self._uuid()
            while existing is None and device_id in historical:
                device_id = self._uuid()
        timestamp = format_utc(utc_now())
        connection.execute(
            """
            INSERT OR IGNORE INTO devices(device_id, device_label, created_at_utc, updated_at_utc)
            VALUES (?, ?, ?, ?)
            """,
            (device_id, label, timestamp, timestamp),
        )
        return device_id

    def _existing_local_device(
        self, connection: sqlite3.Connection, historical: set[str]
    ) -> str | None:
        candidates = {
            str(row[0])
            for row in connection.execute("SELECT device_id FROM devices")
            if str(row[0]) not in historical
        }
        if len(candidates) == 1:
            return next(iter(candidates))
        if not candidates:
            return None
        metadata = connection.execute(
            "SELECT value FROM app_metadata WHERE key LIKE 'portable_import/%'"
        ).fetchall()
        parsed: list[tuple[str, str]] = []
        for row in metadata:
            try:
                value = json.loads(str(row[0]))
                candidate = str(value["current_local_device_id"])
                completed = str(value["completed_at_utc"])
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
            if candidate in candidates:
                parsed.append((completed, candidate))
        return max(parsed)[1] if parsed else None

    def _verify_database(self, connection: sqlite3.Connection) -> None:
        if current_schema_version(connection) != DATABASE_SCHEMA_VERSION:
            raise ImportIntegrityError("staging database migration version is incorrect")
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise ImportIntegrityError(f"staging SQLite integrity check failed: {integrity}")
        report = verify_session_integrity(connection)
        if not report.healthy:
            raise ImportIntegrityError("; ".join(report.errors))
        runtime_count = int(
            connection.execute("SELECT COUNT(*) FROM runtime_session_state").fetchone()[0]
        )
        if runtime_count:
            raise ImportIntegrityError("imported database contains unfinished runtime state")

    def _assert_merge_allowed(self, target: Path) -> None:
        connection = sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True)
        try:
            active = int(
                connection.execute(
                    "SELECT COUNT(*) FROM sessions WHERE status IN ('running', 'paused')"
                ).fetchone()[0]
            )
            runtime = int(
                connection.execute("SELECT COUNT(*) FROM runtime_session_state").fetchone()[0]
            )
        finally:
            connection.close()
        if active or runtime:
            raise ActiveSessionBlocksImportError(
                "import is blocked while an active or unfinished local session exists"
            )

    def _create_backup(self, source: Path, *, reason: str) -> Path:
        backup_dir = self._runtime_root / "database_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = format_utc(utc_now()).replace(":", "-")
        backup = backup_dir / f"lockin_{timestamp}_{reason}.sqlite3"
        try:
            self._sqlite_copy(source, backup)
            with sqlite3.connect(backup) as connection:
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ImportBackupError("database backup failed integrity verification")
            metadata = {
                "created_at_utc": format_utc(utc_now()),
                "source_path": str(source),
                "reason": reason,
                "schema_version": DATABASE_SCHEMA_VERSION,
                "size_bytes": backup.stat().st_size,
                "sha256": _sha256_file(backup),
            }
            backup.with_suffix(".json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            return backup
        except (OSError, sqlite3.Error) as exc:
            raise ImportBackupError(f"could not create verified database backup: {exc}") from exc

    def _sqlite_copy(self, source: Path, destination: Path) -> None:
        source_connection = sqlite3.connect(source)
        destination_connection = sqlite3.connect(destination)
        try:
            source_connection.backup(destination_connection)
        finally:
            destination_connection.close()
            source_connection.close()

    def _insert(
        self, connection: sqlite3.Connection, table: str, values: dict[str, object]
    ) -> None:
        columns = tuple(values)
        placeholders = ", ".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values[column] for column in columns),
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
