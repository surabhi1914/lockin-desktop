"""Read-only verification of SQLite-to-portable export completeness and integrity."""

import csv
import sqlite3
from collections import defaultdict
from pathlib import Path

from app.database.repositories.session_repository import SessionRepository
from app.models.persisted_session import FINAL_SESSION_STATUSES
from app.models.portable_sync import PortableVerificationReport
from app.portability.atomic_csv_writer import read_csv_rows
from app.portability.csv_mapping import portable_row_checksum
from app.portability.csv_validation import validate_csv
from app.services.portable_sync_service import (
    ID_COLUMNS,
    PortableSyncService,
    map_device_values_checksum,
)


class PortableVerificationService:
    def __init__(
        self, connection: sqlite3.Connection, portable_root: Path, backup_root: Path
    ) -> None:
        self._connection = connection
        self._root = portable_root
        self._sync = PortableSyncService(connection, portable_root, backup_root)

    def verify(self, *, local_date: str | None = None) -> PortableVerificationReport:
        errors: list[str] = []
        checked: list[Path] = []
        actual: dict[tuple[str, str], tuple[Path, dict[str, str]]] = {}
        duplicate_keys: set[tuple[str, str]] = set()
        for entity in ("devices", "sessions", "segments", "distractions"):
            paths = (
                [self._root / "devices.csv"]
                if entity == "devices"
                else sorted((self._root / entity).glob("*/*.csv"))
            )
            for path in paths:
                checked.append(path)
                issues = validate_csv(path, entity)
                errors.extend(f"{path}: {issue.error_code}: {issue.message}" for issue in issues)
                if issues:
                    continue
                for row in read_csv_rows(path, entity):
                    date_column = "local_date_started" if entity == "sessions" else "local_date"
                    if entity != "devices" and f"{entity}_{row[date_column][:7]}" not in path.name:
                        errors.append(
                            f"row is in the wrong monthly partition: {row[ID_COLUMNS[entity]]}"
                        )
                    key = (entity, row[ID_COLUMNS[entity]])
                    if key in actual:
                        duplicate_keys.add(key)
                    actual[key] = (path, row)
        errors.extend(
            f"duplicate record across partitions: {key[1]}" for key in sorted(duplicate_keys)
        )

        sessions = tuple(
            item
            for item in SessionRepository(self._connection).all()
            if item.status in FINAL_SESSION_STATUSES
            and item.ended_at_utc is not None
            and (local_date is None or item.local_date_started == local_date)
            and self._connection.execute(
                "SELECT 1 FROM runtime_session_state WHERE session_id = ?", (item.session_id,)
            ).fetchone()
            is None
            and self._connection.execute(
                "SELECT 1 FROM segments WHERE session_id = ? AND ended_at_utc IS NULL",
                (item.session_id,),
            ).fetchone()
            is None
        )
        expected = self._sync.rows_for_sessions(sessions, "2000-01-01T00:00:00Z")
        pending = stale = 0
        ledger_rows = {
            (
                row["record_type"] + "s" if row["record_type"] != "device" else "devices",
                row["record_id"],
            ): row
            for row in self._connection.execute("SELECT * FROM sync_ledger")
        }
        for expected_row in expected:
            key = (expected_row.entity, expected_row.record_id)
            found = actual.get(key)
            if found is None:
                pending += 1
                errors.append(
                    f"missing portable {expected_row.record_type}: {expected_row.record_id}"
                )
                continue
            path, values = found
            checksum = self._row_checksum(expected_row.entity, values)
            if checksum != expected_row.checksum:
                stale += 1
                errors.append(
                    f"checksum mismatch for {expected_row.record_type}: {expected_row.record_id}"
                )
            ledger = ledger_rows.get(key)
            if ledger is None:
                pending += 1
                errors.append(f"missing sync ledger entry: {expected_row.record_id}")
            elif ledger["partition_relative_path"] != path.relative_to(self._root).as_posix():
                stale += 1
                errors.append(f"sync ledger path mismatch: {expected_row.record_id}")

        self._cross_validate(actual, errors)
        return PortableVerificationReport(
            not errors,
            pending,
            stale,
            tuple(errors),
            tuple(checked),
        )

    def _row_checksum(self, entity: str, values: dict[str, str]) -> str:
        if entity == "devices":
            return map_device_values_checksum(values)
        if entity == "sessions":
            return values["record_checksum"]
        return portable_row_checksum(values)

    def _cross_validate(
        self,
        actual: dict[tuple[str, str], tuple[Path, dict[str, str]]],
        errors: list[str],
    ) -> None:
        session_ids = {key[1] for key in actual if key[0] == "sessions"}
        source_totals: dict[str, int] = defaultdict(int)
        focus_totals: dict[str, int] = defaultdict(int)
        pause_totals: dict[str, int] = defaultdict(int)
        distraction_totals: dict[str, int] = defaultdict(int)
        for (entity, record_id), (_path, row) in actual.items():
            if entity in {"segments", "distractions"} and row["session_id"] not in session_ids:
                errors.append(f"orphan {entity[:-1]} row: {record_id}")
            if entity == "segments":
                source_totals[row["source_segment_id"]] += int(row["duration_seconds"])
                target = focus_totals if row["counts_as_focus"] == "true" else pause_totals
                target[row["session_id"]] += int(row["duration_seconds"])
            elif entity == "distractions":
                distraction_totals[row["session_id"]] += 1
        for source_id, total in source_totals.items():
            sqlite_row = self._connection.execute(
                "SELECT duration_seconds FROM segments WHERE segment_id = ?", (source_id,)
            ).fetchone()
            if sqlite_row is not None and int(sqlite_row[0]) != total:
                errors.append(f"split segment duration mismatch: {source_id}")
        for (entity, session_id), (_path, row) in actual.items():
            if entity != "sessions":
                continue
            expected = (
                int(row["actual_focus_seconds"]),
                int(row["total_pause_seconds"]),
                int(row["distraction_count"]),
            )
            found = (
                focus_totals[session_id],
                pause_totals[session_id],
                distraction_totals[session_id],
            )
            if found != expected:
                errors.append(f"session aggregate mismatch: {session_id}")


def count_portable_rows(portable_root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entity in ("devices", "sessions", "segments", "distractions"):
        paths = (
            [portable_root / "devices.csv"]
            if entity == "devices"
            else sorted((portable_root / entity).glob("*/*.csv"))
        )
        count = 0
        for path in paths:
            with path.open("r", encoding="utf-8", newline="") as handle:
                count += sum(1 for _ in csv.DictReader(handle))
        counts[entity] = count
    return counts
