from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QSettings

from app.core.wall_clock import ManualWallClock
from app.database.migrations import initialize_database
from app.database.repositories.device_repository import DeviceRepository
from app.database.unit_of_work import UnitOfWork
from app.services.device_identity_service import DeviceIdentityService


def test_device_identity_is_reused_and_restores_missing_database_row(tmp_path: Path) -> None:
    connection = initialize_database(tmp_path / "database.sqlite3")
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    clock = ManualWallClock(datetime(2026, 7, 16, tzinfo=UTC))
    service = DeviceIdentityService(
        settings, DeviceRepository(connection), UnitOfWork(connection), wall_clock=clock
    )
    first = service.ensure()
    assert service.ensure() == first
    assert connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0] == 1
    connection.execute("DELETE FROM devices WHERE device_id = ?", (first,))
    connection.commit()
    assert service.ensure() == first
    assert connection.execute("SELECT device_label FROM devices").fetchone()[0] == "This device"
