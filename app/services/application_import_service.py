"""GUI-safe verify/preview/stage/restart flow for existing database imports."""

import sqlite3
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from app.core.ids import canonicalize_uuid
from app.portability.import_manifest_service import write_conflict_report
from app.portability.import_models import ImportMode
from app.portability.import_validator import PortableImportValidator
from app.portability.portable_import_service import PortableImportService
from app.services.data_location_service import DataLocationService, resolve_portable_folder
from app.services.device_identity_service import DeviceIdentityService
from app.services.settings_service import SettingsService
from app.ui.dialogs.import_conflict_dialog import ImportConflictDialog
from app.ui.dialogs.import_preview_dialog import ImportPreviewDialog
from app.ui.dialogs.import_result_dialog import show_import_result


class ApplicationImportService:
    def __init__(
        self,
        parent: QWidget,
        runtime_root: Path,
        database_path: Path,
        connection: sqlite3.Connection,
        settings: SettingsService,
        *,
        has_active_session: Callable[[], bool],
        close_application_services: Callable[[], None],
        quit_application: Callable[[], None],
    ) -> None:
        self._parent = parent
        self._runtime_root = runtime_root
        self._database_path = database_path
        self._connection = connection
        self._settings = settings
        self._has_active_session = has_active_session
        self._close_services = close_application_services
        self._quit = quit_application
        self._validator = PortableImportValidator()
        self._importer = PortableImportService(validator=self._validator)

    def request_import(self, selection: Path) -> None:
        if self._blocked():
            QMessageBox.warning(
                self._parent,
                "Portable import blocked",
                "End the active session and resolve any unfinished runtime session before import.",
            )
            return
        report, bundle = self._validator.validate(selection, runtime_root=self._runtime_root)
        if bundle is None or report.errors:
            QMessageBox.warning(
                self._parent,
                "Portable data is not ready",
                "\n".join(report.errors) or "Portable validation failed.",
            )
            return
        if ImportPreviewDialog(report, self._parent).exec() != QDialog.DialogCode.Accepted:
            return
        verification = self._importer.run(
            bundle.root,
            self._runtime_root,
            mode=ImportMode.VERIFY,
            database_path=self._database_path,
        )
        skip_conflicts = False
        if verification.conflicts:
            decision = ImportConflictDialog(verification.conflicts, self._parent).exec()
            if decision != ImportConflictDialog.SKIP_CONFLICTS:
                if decision == 3:
                    write_conflict_report(
                        self._runtime_root / "import_diagnostics",
                        import_id=verification.import_id,
                        source_root=bundle.root,
                        timestamp="verify-only",
                        conflicts=verification.conflicts,
                    )
                return
            skip_conflicts = True
        confirmation = QMessageBox.question(
            self._parent,
            "Import portable history?",
            "LockIn will create a verified backup, promote a staging database, then close. "
            "Restart LockIn afterward.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        try:
            root = resolve_portable_folder(bundle.root, runtime_root=self._runtime_root)
            stored = self._settings.qsettings.value(DeviceIdentityService.SETTINGS_KEY)
            local_device_id = canonicalize_uuid(str(stored)) if stored else None
        except ValueError:
            local_device_id = None
        self._close_services()
        result = self._importer.run(
            root,
            self._runtime_root,
            mode=ImportMode.MERGE,
            database_path=self._database_path,
            skip_conflicts=skip_conflicts,
            local_device_id=local_device_id,
        )
        if result.success:
            DataLocationService(self._settings.qsettings).remember(root)
        show_import_result(result, self._parent)
        QTimer.singleShot(0, self._quit)

    def _blocked(self) -> bool:
        if self._has_active_session():
            return True
        runtime = int(
            self._connection.execute("SELECT COUNT(*) FROM runtime_session_state").fetchone()[0]
        )
        active = int(
            self._connection.execute(
                "SELECT COUNT(*) FROM sessions WHERE status IN ('running', 'paused')"
            ).fetchone()[0]
        )
        return bool(runtime or active)
