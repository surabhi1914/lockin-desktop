"""Capture privacy-safe UI screenshots using a new temporary data store."""

import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings

from app.application import create_application
from app.core.paths import PathConfig
from app.services.settings_service import SettingsService


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    output = repo / "docs" / "images"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lockin-screenshot-") as temporary:
        root = Path(temporary)
        settings = SettingsService(
            QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
        )
        context = create_application(
            config=PathConfig(repo, root / "runtime", root / "portable"),
            settings=settings,
            tray_available=False,
            show_window=True,
        )
        try:
            context.window.resize(1180, 760)
            for page, name in (
                ("home", "lockin-home.png"),
                ("statistics", "lockin-statistics.png"),
            ):
                context.window.navigate(page)
                context.application.processEvents()
                if not context.window.grab().save(str(output / name)):
                    raise RuntimeError(f"Could not save sanitized screenshot {name}")
        finally:
            context.shutdown()
            context.window.hide()
    print(f"Sanitized screenshots: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
