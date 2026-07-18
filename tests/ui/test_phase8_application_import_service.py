import shutil
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from app.application import _offer_new_device_onboarding
from app.core.paths import PathConfig
from app.database.connection import connect_database
from app.portability.import_models import ImportMode, ImportResult
from app.portability.portable_import_service import PortableImportService
from app.services.application_import_service import ApplicationImportService
from app.services.settings_service import SettingsService
from app.ui.dialogs.import_conflict_dialog import ImportConflictDialog
from app.ui.dialogs.import_result_dialog import show_import_result

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PORTABLE_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "portable_data"


def _setup(tmp_path: Path):
    portable = tmp_path / "portable"
    shutil.copytree(PORTABLE_FIXTURE, portable)
    runtime = tmp_path / "runtime"
    imported = PortableImportService().run(portable, runtime, mode=ImportMode.FRESH)
    settings = SettingsService(QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat))
    settings.qsettings.setValue("runtime/device_id", imported.local_device_id)
    connection = connect_database(imported.database_path)
    return portable, runtime, imported, settings, connection


def test_existing_database_gui_flow_promotes_and_requests_restart(
    qapp, qtbot, tmp_path: Path, monkeypatch
) -> None:
    portable, runtime, imported, settings, connection = _setup(tmp_path)
    parent = QWidget()
    qtbot.addWidget(parent)
    monkeypatch.setattr(
        "app.services.application_import_service.ImportPreviewDialog.exec",
        lambda _self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(
        "app.services.application_import_service.show_import_result", lambda *_args: None
    )
    closed: list[bool] = []
    quit_requested: list[bool] = []

    def close() -> None:
        connection.close()
        closed.append(True)

    service = ApplicationImportService(
        parent,
        runtime,
        imported.database_path,
        connection,
        settings,
        has_active_session=lambda: False,
        close_application_services=close,
        quit_application=lambda: quit_requested.append(True),
    )
    service.request_import(portable)
    qapp.processEvents()
    assert closed and quit_requested
    assert settings.qsettings.value("storage/selected_portable_root") == str(portable.resolve())


def test_gui_flow_blocks_active_invalid_and_exports_conflicts(
    qapp, qtbot, tmp_path: Path, monkeypatch
) -> None:
    portable, runtime, imported, settings, connection = _setup(tmp_path)
    parent = QWidget()
    qtbot.addWidget(parent)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, _message, *args, **kwargs: warnings.append(title),
    )
    active = ApplicationImportService(
        parent,
        runtime,
        imported.database_path,
        connection,
        settings,
        has_active_session=lambda: True,
        close_application_services=lambda: None,
        quit_application=lambda: None,
    )
    active.request_import(portable)
    assert warnings[-1] == "Portable import blocked"
    active._has_active_session = lambda: False
    active.request_import(tmp_path / "missing")
    assert warnings[-1] == "Portable data is not ready"

    connection.execute("UPDATE sessions SET record_checksum=?", ("0" * 64,))
    connection.commit()
    monkeypatch.setattr(
        "app.services.application_import_service.ImportPreviewDialog.exec",
        lambda _self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        "app.services.application_import_service.ImportConflictDialog.exec",
        lambda _self: ImportConflictDialog.EXPORT_REPORT,
    )
    active.request_import(portable)
    assert list((runtime / "import_diagnostics").glob("*.json"))
    connection.close()


def test_result_dialog_has_friendly_success_and_failure(qapp, monkeypatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda _p, title, _m: seen.append(title))
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, title, _m: seen.append(title))
    show_import_result(ImportResult(True, "id", ImportMode.FRESH, inserted=2))
    show_import_result(ImportResult(False, "id", ImportMode.MERGE, errors=("safe error",)))
    assert seen == ["Portable import complete", "Portable import not completed"]


def test_new_device_onboarding_verifies_rebuilds_and_remembers_device(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    portable = tmp_path / "existing portable"
    shutil.copytree(PORTABLE_FIXTURE, portable)
    runtime = tmp_path / "new runtime"
    config = PathConfig(tmp_path, runtime, portable)
    monkeypatch.setenv("LOCKIN_SETTINGS_PATH", str(tmp_path / "onboarding.ini"))
    monkeypatch.setattr("app.application.PathConfig.from_environment", lambda: config)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.application.select_portable_data_folder", lambda _parent, _initial: portable
    )
    monkeypatch.setattr(
        "app.application.ImportPreviewDialog.exec",
        lambda _self: QDialog.DialogCode.Accepted,
    )
    assert _offer_new_device_onboarding([]) is True
    assert (runtime / "lockin.sqlite3").exists()
    settings = QSettings(str(tmp_path / "onboarding.ini"), QSettings.Format.IniFormat)
    assert settings.value("runtime/device_id")


def test_onboarding_skips_nonempty_runtime_and_honors_cancel(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    portable = tmp_path / "portable"
    shutil.copytree(PORTABLE_FIXTURE, portable)
    runtime = tmp_path / "runtime"
    imported = PortableImportService().run(portable, runtime, mode=ImportMode.FRESH)
    config = PathConfig(tmp_path, runtime, portable)
    monkeypatch.setattr("app.application.PathConfig.from_environment", lambda: config)
    assert imported.success
    assert _offer_new_device_onboarding([]) is True

    empty_runtime = tmp_path / "empty"
    config = PathConfig(tmp_path, empty_runtime, portable)
    monkeypatch.setattr("app.application.PathConfig.from_environment", lambda: config)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Cancel
    )
    assert _offer_new_device_onboarding([]) is False
