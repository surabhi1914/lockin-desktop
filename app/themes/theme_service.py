"""Load and apply QSS themes without recreating the widget tree."""

from PySide6.QtWidgets import QApplication

from app.services.settings_service import SettingsService
from app.themes.theme_model import Theme
from app.themes.theme_registry import ThemeRegistry


class ThemeLoadError(RuntimeError):
    """Raised when even the safe default stylesheet cannot be loaded."""


class ThemeService:
    def __init__(self, application: QApplication, registry: ThemeRegistry | None = None) -> None:
        self._application = application
        self.registry = registry or ThemeRegistry.standard()
        self.current_theme = self.registry.default
        self.last_error: str | None = None

    def apply(self, theme_id: str) -> Theme:
        requested = self.registry.get_or_default(theme_id)
        theme = requested
        try:
            stylesheet = self._load(theme)
            self.last_error = None
        except OSError as exc:
            self.last_error = f"Could not load theme {requested.display_name}: {exc}"
            theme = self.registry.default
            try:
                stylesheet = self._load(theme)
            except OSError as fallback_exc:
                raise ThemeLoadError(
                    f"Could not load the default {theme.display_name} theme: {fallback_exc}"
                ) from fallback_exc
        self._application.setStyleSheet(stylesheet)
        self.current_theme = theme
        return theme

    def apply_saved(self, settings: SettingsService) -> Theme:
        theme = self.apply(settings.theme_id())
        if settings.theme_id() != theme.theme_id:
            settings.set_theme_id(theme.theme_id)
        return theme

    @staticmethod
    def _load(theme: Theme) -> str:
        return theme.stylesheet_path.read_text(encoding="utf-8")
