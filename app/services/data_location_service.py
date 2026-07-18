"""Resolve and remember a validated user-selected portable-data folder."""

from pathlib import Path

from PySide6.QtCore import QSettings

from app.portability.import_errors import ImportValidationError

REQUIRED_ROOT_FILES = (
    "manifest.json",
    "devices.csv",
    "categories.csv",
    "quotes.csv",
    "daily_goals.csv",
)
REQUIRED_DIRECTORIES = ("sessions", "segments", "distractions")


def resolve_portable_folder(selection: Path, *, runtime_root: Path | None = None) -> Path:
    selected = selection.expanduser().resolve()
    direct = selected
    child = selected / "portable_data"
    if not (direct / "manifest.json").is_file() and (child / "manifest.json").is_file():
        direct = child.resolve()
    if not direct.is_dir():
        raise ImportValidationError(f"portable selection is not a directory: {direct}")
    if runtime_root is not None and direct == runtime_root.resolve():
        raise ImportValidationError("runtime and portable roots must be different")
    for name in REQUIRED_ROOT_FILES:
        if not (direct / name).is_file():
            raise ImportValidationError(f"portable root is missing required file: {name}")
    for name in REQUIRED_DIRECTORIES:
        if not (direct / name).is_dir():
            raise ImportValidationError(f"portable root is missing required directory: {name}")
    return direct


class DataLocationService:
    SETTINGS_KEY = "storage/selected_portable_root"

    def __init__(self, settings: QSettings) -> None:
        self._settings = settings

    def remember(self, path: Path) -> None:
        self._settings.setValue(self.SETTINGS_KEY, str(path.resolve()))
        self._settings.sync()
        if self._settings.status() is not QSettings.Status.NoError:
            raise ImportValidationError("selected portable folder could not be saved")

    def selected(self) -> Path | None:
        value = self._settings.value(self.SETTINGS_KEY)
        return None if not value else Path(str(value)).expanduser().resolve()
