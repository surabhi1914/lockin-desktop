from pathlib import Path

import pytest

from app.themes.theme_model import Theme
from app.themes.theme_registry import ThemeRegistry


def test_five_unique_standard_themes_exist() -> None:
    registry = ThemeRegistry.standard()
    assert [theme.theme_id for theme in registry.themes] == [
        "midnight",
        "forest",
        "slate",
        "warm_neutral",
        "light",
    ]
    assert registry.default.theme_id == "midnight"
    assert all(theme.stylesheet_path.is_file() for theme in registry.themes)
    assert len({theme.accent_color for theme in registry.themes}) == 5


def test_registry_rejects_duplicates_and_unknown_default(tmp_path: Path) -> None:
    theme = Theme("one", "One", True, tmp_path / "one.qss", "#000000", "One")
    with pytest.raises(ValueError, match="Duplicate"):
        ThemeRegistry((theme, theme))
    with pytest.raises(ValueError, match="default"):
        ThemeRegistry((theme,), default_id="missing")
    registry = ThemeRegistry((theme,), default_id="one")
    with pytest.raises(KeyError, match="Unknown"):
        registry.get("missing")
    assert registry.get_or_default("missing") == theme
