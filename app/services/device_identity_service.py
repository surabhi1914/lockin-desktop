"""Stable device-local UUID identity backed by QSettings and SQLite."""

from PySide6.QtCore import QSettings

from app.core.ids import canonicalize_uuid, new_uuid4
from app.core.time_utils import format_utc
from app.core.wall_clock import SystemWallClock, WallClock, require_utc
from app.database.repositories.device_repository import DeviceRepository
from app.database.unit_of_work import UnitOfWork
from app.models.errors import SessionPersistenceError


class DeviceIdentityService:
    SETTINGS_KEY = "runtime/device_id"

    def __init__(
        self,
        settings: QSettings,
        repository: DeviceRepository,
        unit_of_work: UnitOfWork,
        *,
        wall_clock: WallClock | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._clock = wall_clock or SystemWallClock()

    def ensure(self) -> str:
        stored = self._settings.value(self.SETTINGS_KEY)
        try:
            device_id = canonicalize_uuid(str(stored)) if stored else new_uuid4()
        except ValueError:
            device_id = new_uuid4()
        if stored != device_id:
            self._settings.setValue(self.SETTINGS_KEY, device_id)
            self._settings.sync()
            if self._settings.status() is not QSettings.Status.NoError:
                raise SessionPersistenceError("device-local identity settings could not be saved")
        timestamp = format_utc(require_utc(self._clock.now_utc()))
        with self._unit_of_work:
            self._repository.insert_if_missing(device_id, "This device", timestamp)
        return device_id
