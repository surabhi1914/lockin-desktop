"""Verify and rebuild a new installation while preserving historical device IDs."""

import sqlite3
from pathlib import Path

from PySide6.QtCore import QSettings

from app.core.ids import canonicalize_uuid
from app.portability.import_models import ImportMode, ImportReadinessReport, ImportResult
from app.portability.import_validator import PortableImportValidator
from app.portability.portable_import_service import PortableImportService
from app.services.data_location_service import DataLocationService, resolve_portable_folder
from app.services.device_identity_service import DeviceIdentityService


class NewDeviceSetupService:
    def __init__(self, settings: QSettings) -> None:
        self._settings = settings
        self._locations = DataLocationService(settings)
        self._validator = PortableImportValidator()
        self._importer = PortableImportService(validator=self._validator)

    def verify(self, selection: Path, runtime_root: Path) -> ImportReadinessReport:
        report, _bundle = self._validator.validate(selection, runtime_root=runtime_root)
        return report

    def rebuild(self, selection: Path, runtime_root: Path) -> ImportResult:
        root = resolve_portable_folder(selection, runtime_root=runtime_root)
        stored = self._settings.value(DeviceIdentityService.SETTINGS_KEY)
        local_device_id: str | None = None
        if stored:
            try:
                local_device_id = canonicalize_uuid(str(stored))
            except ValueError:
                local_device_id = None
        result = self._importer.run(
            root,
            runtime_root,
            mode=ImportMode.FRESH,
            local_device_id=local_device_id,
            allow_replace=self.runtime_is_empty(runtime_root),
        )
        if result.success and result.local_device_id is not None:
            self._settings.setValue(DeviceIdentityService.SETTINGS_KEY, result.local_device_id)
            self._locations.remember(root)
            self._settings.sync()
        return result

    @staticmethod
    def runtime_is_empty(runtime_root: Path) -> bool:
        database = runtime_root / "lockin.sqlite3"
        if not database.exists() or database.stat().st_size == 0:
            return True
        try:
            connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
            tables = {
                str(row[0])
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if "sessions" not in tables:
                return True
            counts = sum(
                int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in ("sessions", "segments", "distractions", "runtime_session_state")
            )
            return counts == 0
        finally:
            if "connection" in locals():
                connection.close()
