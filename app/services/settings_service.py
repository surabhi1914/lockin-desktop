"""Typed persistent Phase 1 UI preferences backed by QSettings."""

import os
from enum import StrEnum

from PySide6.QtCore import QByteArray, QSettings


class SidebarStartup(StrEnum):
    REMEMBER = "remember"
    EXPANDED = "expanded"
    COLLAPSED = "collapsed"


class CloseBehavior(StrEnum):
    EXIT = "exit"
    MINIMIZE_TO_TRAY = "minimize_to_tray"


class SettingsService:
    """Own the explicit, non-sensitive UI defaults allowed through Phase 3."""

    ORGANIZATION = "LockIn"
    APPLICATION = "LockInDesktop"
    DEFAULT_THEME_ID = "midnight"
    DEFAULT_PAGE_ID = "home"
    VALID_PAGE_IDS = frozenset(
        {"home", "focus_setup", "statistics", "history", "categories", "quotes", "settings"}
    )
    _KEYS = (
        "ui/theme_id",
        "window/geometry",
        "window/state",
        "sidebar/collapsed",
        "sidebar/startup",
        "tray/minimize_to_tray",
        "window/close_behavior",
        "navigation/last_page",
        "focus_setup/last_category_id",
        "focus_setup/duration_hours",
        "focus_setup/duration_minutes",
        "focus_setup/start_in_fullscreen",
        "focus_setup/show_quotes",
        "focus_setup/play_completion_sound",
        "focus_setup/overtime_enabled",
        "focus_setup/start_ritual_enabled",
        "audio/completion_enabled",
        "audio/completion_volume",
    )

    def __init__(self, settings: QSettings | None = None) -> None:
        if settings is not None:
            self._settings = settings
            return
        isolated_path = os.environ.get("LOCKIN_SETTINGS_PATH")
        self._settings = (
            QSettings(isolated_path, QSettings.Format.IniFormat)
            if isolated_path
            else QSettings(self.ORGANIZATION, self.APPLICATION)
        )

    @property
    def qsettings(self) -> QSettings:
        return self._settings

    def theme_id(self) -> str:
        value = self._settings.value("ui/theme_id", self.DEFAULT_THEME_ID)
        return value if isinstance(value, str) and value.strip() else self.DEFAULT_THEME_ID

    def set_theme_id(self, theme_id: str) -> None:
        self._settings.setValue("ui/theme_id", theme_id)

    def geometry(self) -> QByteArray | None:
        return self._byte_array("window/geometry")

    def set_geometry(self, geometry: QByteArray) -> None:
        self._settings.setValue("window/geometry", geometry)

    def window_state(self) -> QByteArray | None:
        return self._byte_array("window/state")

    def set_window_state(self, state: QByteArray) -> None:
        self._settings.setValue("window/state", state)

    def sidebar_collapsed(self) -> bool:
        return self._boolean("sidebar/collapsed", False)

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        self._settings.setValue("sidebar/collapsed", collapsed)

    def sidebar_startup(self) -> SidebarStartup:
        value = self._settings.value("sidebar/startup", SidebarStartup.REMEMBER.value)
        try:
            return SidebarStartup(str(value))
        except ValueError:
            return SidebarStartup.REMEMBER

    def set_sidebar_startup(self, behavior: SidebarStartup) -> None:
        self._settings.setValue("sidebar/startup", behavior.value)

    def minimize_to_tray(self) -> bool:
        return self._boolean("tray/minimize_to_tray", False)

    def set_minimize_to_tray(self, enabled: bool) -> None:
        self._settings.setValue("tray/minimize_to_tray", enabled)

    def close_behavior(self) -> CloseBehavior:
        value = self._settings.value("window/close_behavior", CloseBehavior.EXIT.value)
        try:
            return CloseBehavior(str(value))
        except ValueError:
            return CloseBehavior.EXIT

    def set_close_behavior(self, behavior: CloseBehavior) -> None:
        self._settings.setValue("window/close_behavior", behavior.value)

    def last_page_id(self) -> str:
        value = self._settings.value("navigation/last_page", self.DEFAULT_PAGE_ID)
        if isinstance(value, str) and value in self.VALID_PAGE_IDS:
            return value
        return self.DEFAULT_PAGE_ID

    def set_last_page_id(self, page_id: str) -> None:
        self._settings.setValue(
            "navigation/last_page",
            page_id if page_id in self.VALID_PAGE_IDS else self.DEFAULT_PAGE_ID,
        )

    def focus_last_category_id(self) -> str | None:
        value = self._settings.value("focus_setup/last_category_id")
        return value if isinstance(value, str) and value.strip() else None

    def set_focus_last_category_id(self, category_id: str) -> None:
        self._settings.setValue("focus_setup/last_category_id", category_id)

    def focus_duration(self) -> tuple[int, int]:
        hours = self._bounded_integer("focus_setup/duration_hours", 0, 0, 167)
        minutes = self._bounded_integer("focus_setup/duration_minutes", 50, 0, 59)
        if hours == 0 and minutes == 0:
            return 0, 50
        return hours, minutes

    def set_focus_duration(self, hours: int, minutes: int) -> None:
        if not 0 <= hours <= 167 or not 0 <= minutes <= 59:
            raise ValueError("focus duration settings are outside UI limits")
        if hours == 0 and minutes == 0:
            raise ValueError("focus duration must be at least one minute")
        self._settings.setValue("focus_setup/duration_hours", hours)
        self._settings.setValue("focus_setup/duration_minutes", minutes)

    def focus_start_in_fullscreen(self) -> bool:
        return self._boolean("focus_setup/start_in_fullscreen", True)

    def set_focus_start_in_fullscreen(self, enabled: bool) -> None:
        self._settings.setValue("focus_setup/start_in_fullscreen", enabled)

    def focus_show_quotes(self) -> bool:
        return self._boolean("focus_setup/show_quotes", True)

    def set_focus_show_quotes(self, enabled: bool) -> None:
        self._settings.setValue("focus_setup/show_quotes", enabled)

    def focus_play_completion_sound(self) -> bool:
        return self._boolean("focus_setup/play_completion_sound", True)

    def set_focus_play_completion_sound(self, enabled: bool) -> None:
        self._settings.setValue("focus_setup/play_completion_sound", enabled)

    def focus_overtime_enabled(self) -> bool:
        return self._boolean("focus_setup/overtime_enabled", True)

    def set_focus_overtime_enabled(self, enabled: bool) -> None:
        self._settings.setValue("focus_setup/overtime_enabled", enabled)

    def focus_start_ritual_enabled(self) -> bool:
        return self._boolean("focus_setup/start_ritual_enabled", True)

    def set_focus_start_ritual_enabled(self, enabled: bool) -> None:
        self._settings.setValue("focus_setup/start_ritual_enabled", enabled)

    def completion_sound_enabled(self) -> bool:
        return self._boolean("audio/completion_enabled", True)

    def set_completion_sound_enabled(self, enabled: bool) -> None:
        self._settings.setValue("audio/completion_enabled", enabled)

    def completion_sound_volume(self) -> int:
        return self._bounded_integer("audio/completion_volume", 60, 0, 100)

    def set_completion_sound_volume(self, volume: int) -> None:
        if isinstance(volume, bool) or not isinstance(volume, int) or not 0 <= volume <= 100:
            raise ValueError("completion sound volume must be from 0 to 100")
        self._settings.setValue("audio/completion_volume", volume)

    def reset_phase1_defaults(self) -> None:
        for key in self._KEYS:
            self._settings.remove(key)
        self._settings.sync()

    def sync(self) -> None:
        self._settings.sync()

    def _byte_array(self, key: str) -> QByteArray | None:
        value = self._settings.value(key)
        if isinstance(value, QByteArray) and not value.isEmpty():
            return value
        if isinstance(value, bytes) and value:
            return QByteArray(value)
        return None

    def _boolean(self, key: str, default: bool) -> bool:
        value = self._settings.value(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in {0, 1}:
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
        return default

    def _bounded_integer(self, key: str, default: int, minimum: int, maximum: int) -> int:
        value = self._settings.value(key, default)
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            integer = value
        elif isinstance(value, str):
            try:
                integer = int(value)
            except ValueError:
                return default
        else:
            return default
        return integer if minimum <= integer <= maximum else default
