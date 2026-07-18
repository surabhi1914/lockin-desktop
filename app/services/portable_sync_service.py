"""SQLite-authoritative, idempotent portable CSV export."""

import sqlite3
from dataclasses import replace
from pathlib import Path

from app.core.time_utils import format_utc, utc_now
from app.database.repositories.device_repository import DeviceRepository
from app.database.repositories.distraction_repository import DistractionRepository
from app.database.repositories.segment_repository import SegmentRepository
from app.database.repositories.session_repository import SessionRepository
from app.database.repositories.sync_ledger_repository import SyncLedgerRepository
from app.models.persisted_session import FINAL_SESSION_STATUSES, PersistedSession
from app.models.portable_sync import PortableRow, PortableSyncResult, SyncCounts
from app.models.sync_ledger_entry import SyncLedgerEntry
from app.portability.atomic_csv_writer import AtomicCsvWriter, read_csv_rows
from app.portability.device_csv_mapper import map_device
from app.portability.distraction_csv_mapper import map_distraction
from app.portability.errors import (
    PortableDuplicateRecordError,
    PortableLedgerConflictError,
    PortablePartitionError,
    PortableSyncError,
)
from app.portability.manifest import PortableManifest, load_manifest, save_manifest_atomic
from app.portability.partition_manager import select_partition
from app.portability.segment_csv_mapper import map_segment
from app.portability.session_csv_mapper import map_session

ENTITY_ORDER = ("devices", "sessions", "segments", "distractions")
ID_COLUMNS = {
    "devices": "device_id",
    "sessions": "session_id",
    "segments": "segment_id",
    "distractions": "distraction_id",
}
SORT_COLUMNS = {
    "devices": ("device_id",),
    "sessions": (
        "started_at_local",
        "started_at_utc",
        "device_id",
        "session_sequence",
        "session_id",
    ),
    "segments": ("started_at_utc", "session_id", "segment_sequence", "midnight_part_number"),
    "distractions": ("marked_at_utc", "session_id", "distraction_id"),
}


class PortableSyncService:
    def __init__(
        self, connection: sqlite3.Connection, portable_root: Path, backup_root: Path
    ) -> None:
        self._connection = connection
        self._root = portable_root
        self._manifest_path = portable_root / "manifest.json"
        self._writer = AtomicCsvWriter(backup_root)
        self._sessions = SessionRepository(connection)
        self._segments = SegmentRepository(connection)
        self._distractions = DistractionRepository(connection)
        self._devices = DeviceRepository(connection)
        self._ledger = SyncLedgerRepository(connection)

    def sync_all(self) -> PortableSyncResult:
        return self._sync(self._eligible_sessions())

    def sync_session(self, session_id: str) -> PortableSyncResult:
        session = self._sessions.get(session_id)
        sessions = () if session is None or not self._eligible(session) else (session,)
        if not sessions:
            return self._failure(f"session is not eligible for portable export: {session_id}")
        return self._sync(sessions)

    def rows_for_sessions(
        self, sessions: tuple[PersistedSession, ...], exported_at_utc: str
    ) -> tuple[PortableRow, ...]:
        rows: list[PortableRow] = [map_device(device) for device in self._devices.list_all()]
        for session in sessions:
            rows.append(map_session(session, exported_at_utc))
            for segment in self._segments.list_for_session(session.session_id):
                if segment.ended_at_utc is None:
                    raise PortableSyncError(f"session has an open segment: {session.session_id}")
                rows.extend(
                    map_segment(
                        segment,
                        exported_at_utc,
                        parent_started_at_utc=session.started_at_utc,
                    )
                )
            rows.extend(
                map_distraction(item, exported_at_utc)
                for item in self._distractions.list_for_session(session.session_id)
            )
        return tuple(rows)

    def _sync(self, sessions: tuple[PersistedSession, ...]) -> PortableSyncResult:
        timestamp = format_utc(utc_now())
        touched: list[Path] = []
        warnings: list[str] = []
        totals = dict.fromkeys(ENTITY_ORDER, 0)
        skipped = repaired = 0
        try:
            manifest = load_manifest(self._manifest_path)
            rows = self.rows_for_sessions(sessions, timestamp)
            for row in rows:
                action, path, oversized = self._write_row(row, manifest, timestamp)
                if action == "skipped":
                    skipped += 1
                else:
                    totals[row.entity] += 1
                    if action == "repaired":
                        repaired += 1
                    if path is not None and path not in touched:
                        touched.append(path)
                if oversized:
                    warnings.append(
                        f"single {row.entity} row exceeds partition threshold: {row.record_id}"
                    )
            updated = replace(
                manifest,
                updated_at_utc=timestamp,
                last_successful_sync_at_utc=timestamp,
            )
            save_manifest_atomic(self._manifest_path, updated)
            return PortableSyncResult(
                True,
                SyncCounts(
                    devices=totals["devices"],
                    sessions=totals["sessions"],
                    segments=totals["segments"],
                    distractions=totals["distractions"],
                    skipped=skipped,
                    repaired=repaired,
                ),
                tuple(touched),
                tuple(warnings),
                (),
                timestamp,
            )
        except (PortableSyncError, OSError, ValueError) as exc:
            self._connection.rollback()
            return PortableSyncResult(
                False,
                SyncCounts(skipped=skipped, repaired=repaired, errors=1),
                tuple(touched),
                tuple(warnings),
                (str(exc),),
                timestamp,
            )

    def _write_row(
        self, row: PortableRow, manifest: PortableManifest, timestamp: str
    ) -> tuple[str, Path | None, bool]:
        matches = self._find_record(row.entity, row.record_id)
        if len(matches) > 1:
            raise PortableDuplicateRecordError(f"duplicate portable record: {row.record_id}")
        ledger = self._ledger.get(row.record_type, row.record_id)
        expected_path = self._expected_path(row, manifest)
        existing_path: Path | None = matches[0][0] if matches else None
        existing_row: dict[str, str] | None = matches[0][1] if matches else None
        if existing_path is not None and row.entity != "devices":
            expected_month = self._month_prefix(row)
            if expected_month not in existing_path.name:
                raise PortablePartitionError(
                    f"record is in the wrong monthly partition: {row.record_id}: {existing_path}"
                )
        if ledger is not None and existing_path is not None:
            ledger_path = (self._root / ledger.partition_relative_path).resolve()
            if ledger_path != existing_path.resolve():
                raise PortableLedgerConflictError(
                    f"ledger path conflicts with portable row: {row.record_id}"
                )
        existing_checksum = None if existing_row is None else existing_row.get("record_checksum")
        if row.entity == "devices" and existing_row is not None:
            existing_checksum = map_device_values_checksum(existing_row)
        if existing_row is not None and existing_checksum == row.checksum:
            assert existing_path is not None
            if ledger is None or ledger.record_checksum != row.checksum:
                self._save_ledger(row, existing_path, timestamp)
                return "repaired", existing_path, False
            return "skipped", None, False

        ledger_destination: Path | None = None
        if ledger is not None and existing_path is None:
            ledger_destination = (self._root / ledger.partition_relative_path).resolve()
            if row.entity != "devices" and self._month_prefix(row) not in ledger_destination.name:
                raise PortableLedgerConflictError(
                    f"stale ledger points to the wrong monthly partition: {row.record_id}"
                )
        destination = existing_path or ledger_destination or expected_path
        current = read_csv_rows(destination, row.entity)
        id_column = ID_COLUMNS[row.entity]
        current = [item for item in current if item[id_column] != row.record_id]
        current.append(row.values)
        current.sort(
            key=lambda item: tuple(
                _sort_value(item.get(key, "")) for key in SORT_COLUMNS[row.entity]
            )
        )
        oversized = self._encoded_row_size(row) > self._partition_limit(manifest)
        self._writer.replace(destination, row.entity, current)
        installed = self._find_record(row.entity, row.record_id)
        if len(installed) != 1:
            raise PortableSyncError(f"portable row was not installed exactly once: {row.record_id}")
        self._save_ledger(row, destination, timestamp)
        return (
            ("repaired" if ledger is not None or existing_row is not None else "written"),
            destination,
            oversized,
        )

    def _expected_path(self, row: PortableRow, manifest: PortableManifest) -> Path:
        if row.entity == "devices":
            return self._root / "devices.csv"
        if row.local_date is None:
            raise PortablePartitionError(f"partitioned row has no local date: {row.record_id}")
        config = manifest.partitioning
        return select_partition(
            self._root,
            row.entity,
            row.local_date,
            max_file_size_bytes=config.max_file_size_bytes,
            part_number_width=config.part_number_width,
            row=row.values,
        )

    def _find_record(self, entity: str, record_id: str) -> list[tuple[Path, dict[str, str]]]:
        paths = (
            [self._root / "devices.csv"]
            if entity == "devices"
            else sorted((self._root / entity).glob("*/*.csv"))
        )
        found: list[tuple[Path, dict[str, str]]] = []
        key = ID_COLUMNS[entity]
        for path in paths:
            for row in read_csv_rows(path, entity):
                if row[key] == record_id:
                    found.append((path, row))
        return found

    def _save_ledger(self, row: PortableRow, path: Path, timestamp: str) -> None:
        self._ledger.upsert(
            SyncLedgerEntry(
                row.record_type,
                row.record_id,
                path.relative_to(self._root).as_posix(),
                row.checksum,
                timestamp,
            )
        )
        self._connection.commit()

    def _eligible_sessions(self) -> tuple[PersistedSession, ...]:
        return tuple(session for session in self._sessions.all() if self._eligible(session))

    def _eligible(self, session: PersistedSession) -> bool:
        if session.status not in FINAL_SESSION_STATUSES or session.ended_at_utc is None:
            return False
        unresolved = self._connection.execute(
            "SELECT 1 FROM runtime_session_state WHERE session_id = ?", (session.session_id,)
        ).fetchone()
        open_segment = self._connection.execute(
            "SELECT 1 FROM segments WHERE session_id = ? AND ended_at_utc IS NULL",
            (session.session_id,),
        ).fetchone()
        return unresolved is None and open_segment is None

    def _partition_limit(self, manifest: PortableManifest) -> int:
        return manifest.partitioning.max_file_size_bytes

    def _encoded_row_size(self, row: PortableRow) -> int:
        import csv
        import io

        buffer = io.StringIO(newline="")
        csv.DictWriter(buffer, fieldnames=tuple(row.values), lineterminator="\n").writerow(
            row.values
        )
        return len(buffer.getvalue().encode("utf-8"))

    def _month_prefix(self, row: PortableRow) -> str:
        assert row.local_date is not None
        return f"{row.entity}_{row.local_date[:7]}"

    def _failure(self, message: str) -> PortableSyncResult:
        timestamp = format_utc(utc_now())
        return PortableSyncResult(False, SyncCounts(errors=1), (), (), (message,), timestamp)


def _sort_value(value: str) -> str | int:
    try:
        return int(value)
    except ValueError:
        return value


def map_device_values_checksum(values: dict[str, str]) -> str:
    from app.core.checksums import record_checksum

    return record_checksum(values)
