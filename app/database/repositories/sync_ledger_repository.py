"""Sync-ledger bookkeeping without transaction ownership."""

import sqlite3

from app.models.sync_ledger_entry import SyncLedgerEntry


class SyncLedgerRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, record_type: str, record_id: str) -> SyncLedgerEntry | None:
        row = self._connection.execute(
            "SELECT * FROM sync_ledger WHERE record_type = ? AND record_id = ?",
            (record_type, record_id),
        ).fetchone()
        return None if row is None else SyncLedgerEntry.from_row(row)

    def upsert(self, entry: SyncLedgerEntry) -> None:
        self._connection.execute(
            """
            INSERT INTO sync_ledger (
              record_type, record_id, partition_relative_path,
              record_checksum, exported_at_utc
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(record_type, record_id) DO UPDATE SET
              partition_relative_path = excluded.partition_relative_path,
              record_checksum = excluded.record_checksum,
              exported_at_utc = excluded.exported_at_utc
            """,
            (
                entry.record_type,
                entry.record_id,
                entry.partition_relative_path,
                entry.record_checksum,
                entry.exported_at_utc,
            ),
        )

    def list_all(self) -> tuple[SyncLedgerEntry, ...]:
        rows = self._connection.execute(
            "SELECT * FROM sync_ledger ORDER BY record_type, record_id"
        ).fetchall()
        return tuple(SyncLedgerEntry.from_row(row) for row in rows)

    def delete(self, record_type: str, record_id: str) -> None:
        self._connection.execute(
            "DELETE FROM sync_ledger WHERE record_type = ? AND record_id = ?",
            (record_type, record_id),
        )
