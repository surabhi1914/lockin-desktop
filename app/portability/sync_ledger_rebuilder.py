"""Rebuild device-local export bookkeeping from verified portable source rows."""

import sqlite3

from app.database.repositories.sync_ledger_repository import SyncLedgerRepository
from app.models.sync_ledger_entry import SyncLedgerEntry
from app.portability.import_models import PortableImportBundle, PortableSourceRow


class SyncLedgerRebuilder:
    def rebuild(
        self,
        connection: sqlite3.Connection,
        bundle: PortableImportBundle,
        *,
        excluded: set[tuple[str, str]] | None = None,
    ) -> int:
        repository = SyncLedgerRepository(connection)
        excluded_keys = excluded or set()
        for entity, record_id in excluded_keys:
            if entity in {"devices", "sessions", "segments", "distractions"}:
                record_type = entity[:-1] if entity != "devices" else "device"
                repository.delete(record_type, record_id)
        count = 0
        for entity in ("devices", "sessions", "segments", "distractions"):
            for row in bundle.rows[entity]:
                if (entity, row.record_id) in excluded_keys:
                    continue
                repository.upsert(
                    SyncLedgerEntry(
                        entity[:-1] if entity != "devices" else "device",
                        row.record_id,
                        row.location.path.relative_to(bundle.root).as_posix(),
                        row.checksum,
                        self._exported_at(row),
                    )
                )
                count += 1
        return count

    def _exported_at(self, row: PortableSourceRow) -> str:
        if "exported_at_utc" in row.values:
            return row.values["exported_at_utc"]
        return row.values["updated_at_utc"]
