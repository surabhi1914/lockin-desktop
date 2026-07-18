"""Read-only post-import database, ledger, and portable comparison."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.portability.import_conflict_detector import ImportConflictDetector
from app.portability.import_models import ImportMode
from app.portability.import_validator import PortableImportValidator
from app.services.session_integrity_service import verify_session_integrity


@dataclass(frozen=True, slots=True)
class DatabasePortableComparison:
    healthy: bool
    missing_in_database: int
    missing_in_portable: int
    conflicts: int
    ledger_mismatches: int
    errors: tuple[str, ...]


def compare_database_to_portable(
    database_path: Path, portable_root: Path
) -> DatabasePortableComparison:
    report, bundle = PortableImportValidator().validate(portable_root)
    if bundle is None:
        return DatabasePortableComparison(False, 0, 0, 0, 0, report.errors)
    plan = ImportConflictDetector().plan(bundle, database_path, mode=ImportMode.MERGE)
    missing = sum(item.action == "insert" for item in plan.operations)
    errors = [item.reason for item in plan.conflicts]
    ledger_mismatches = 0
    connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        integrity = verify_session_integrity(connection)
        errors.extend(integrity.errors)
        ledger = {
            (row["record_type"], row["record_id"]): row
            for row in connection.execute("SELECT * FROM sync_ledger")
        }
        portable_ids = {
            "devices": {row.record_id for row in bundle.rows["devices"]},
            "sessions": {row.record_id for row in bundle.rows["sessions"]},
            "segments": {row.segment_id for row in bundle.logical_segments},
            "distractions": {row.record_id for row in bundle.rows["distractions"]},
        }
        missing_portable = 0
        for table, id_column in (
            ("devices", "device_id"),
            ("sessions", "session_id"),
            ("segments", "segment_id"),
            ("distractions", "distraction_id"),
        ):
            database_ids = {
                str(row[0]) for row in connection.execute(f"SELECT {id_column} FROM {table}")
            }
            missing_portable += len(database_ids - portable_ids[table])
        for entity in ("devices", "sessions", "segments", "distractions"):
            record_type = entity[:-1] if entity != "devices" else "device"
            for row in bundle.rows[entity]:
                entry = ledger.get((record_type, row.record_id))
                relative = row.location.path.relative_to(bundle.root).as_posix()
                if (
                    entry is None
                    or entry["record_checksum"] != row.checksum
                    or entry["partition_relative_path"] != relative
                ):
                    ledger_mismatches += 1
    finally:
        connection.close()
    if ledger_mismatches:
        errors.append(f"sync ledger mismatches: {ledger_mismatches}")
    return DatabasePortableComparison(
        not errors and missing == 0,
        missing,
        missing_portable,
        len(plan.conflicts),
        ledger_mismatches,
        tuple(errors),
    )
