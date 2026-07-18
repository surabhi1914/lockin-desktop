"""Non-interactive production health diagnostics."""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication

from app.bootstrap import run_phase0_bootstrap
from app.core.paths import PathConfig, ensure_directory
from app.core.resources import ResourceLocator
from app.core.runtime_environment import is_frozen
from app.database.migrations import current_schema_version
from app.version import __version__


def run_health_check(output_path: Path) -> int:
    """Write a privacy-safe JSON report and return zero only when every check passes."""
    report: dict[str, Any] = {
        "version": __version__,
        "executable": Path(sys.executable).name,
        "frozen": is_frozen(),
        "result": "failed",
    }
    errors: list[str] = []
    try:
        config = PathConfig.from_environment(create_runtime=True, create_portable=True)
        _verify_writable(config.runtime_root)
        bootstrap = run_phase0_bootstrap(config=config)
        if not bootstrap.success:
            errors.extend(bootstrap.errors)
        database_status = _database_status(config.database_path)
        locator = ResourceLocator.standard()
        starter_root = (
            locator.required_directory("starter_resources")
            if is_frozen()
            else locator.required_directory("packaging", "starter_resources")
        )
        resources = {
            "themes": str(locator.required_directory("app", "themes").name),
            "focus_style": locator.required("app", "themes", "focus_screen.qss").name,
            "sound": locator.required("app", "assets", "lockin_completion.wav").name,
            "icon": locator.required("app", "assets", "icons", "lockin.ico").name,
            "starter_resources": starter_root.name,
        }
        application = QApplication.instance()
        owns_application = application is None
        if application is None:
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            application = QApplication(["LockIn-health-check"])
        assert isinstance(application, QApplication)
        qt_status = {"platform": application.platformName(), "available": True}
        if owns_application:
            application.quit()
        report.update(
            {
                "resources": resources,
                "paths": {
                    "runtime": str(config.runtime_root),
                    "portable": str(config.portable_root),
                    "logs": str(config.logs_root),
                    "backups": str(config.backups_root),
                    "diagnostics": str(config.diagnostics_root),
                },
                "database": database_status,
                "qt": qt_status,
            }
        )
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
        errors.append(str(exc))
    report["errors"] = errors
    report["result"] = "ok" if not errors else "failed"
    _write_json_atomic(output_path, report)
    return 0 if not errors else 1


def _verify_writable(root: Path) -> None:
    ensure_directory(root)
    descriptor, name = tempfile.mkstemp(prefix=".lockin-health-", dir=root)
    os.close(descriptor)
    Path(name).unlink(missing_ok=True)


def _database_status(path: Path) -> dict[str, object]:
    with sqlite3.connect(path) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        version = current_schema_version(connection)
    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {integrity}")
    return {"integrity": integrity, "schema_version": version, "available": True}


def _write_json_atomic(path: Path, report: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
