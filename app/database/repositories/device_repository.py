"""Device identity persistence without transaction ownership."""

import sqlite3

from app.models.persisted_device import PersistedDevice


class DeviceRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def exists(self, device_id: str) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM devices WHERE device_id = ?", (device_id,)
            ).fetchone()
            is not None
        )

    def insert_if_missing(self, device_id: str, label: str, timestamp: str) -> None:
        self._connection.execute(
            """
            INSERT OR IGNORE INTO devices(device_id, device_label, created_at_utc, updated_at_utc)
            VALUES (?, ?, ?, ?)
            """,
            (device_id, label, timestamp, timestamp),
        )

    def list_all(self) -> tuple[PersistedDevice, ...]:
        rows = self._connection.execute("SELECT * FROM devices ORDER BY device_id").fetchall()
        return tuple(PersistedDevice.from_row(row) for row in rows)
