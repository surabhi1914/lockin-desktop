"""Validated registry of the five Phase 1 themes."""

from collections.abc import Iterable
from types import MappingProxyType
from typing import Final

from app.core.resources import ResourceLocator
from app.themes.theme_model import Theme

DEFAULT_THEME_ID: Final = "midnight"


class ThemeRegistry:
    def __init__(self, themes: Iterable[Theme], *, default_id: str = DEFAULT_THEME_ID) -> None:
        by_id: dict[str, Theme] = {}
        for theme in themes:
            if theme.theme_id in by_id:
                raise ValueError(f"Duplicate theme ID: {theme.theme_id}")
            by_id[theme.theme_id] = theme
        if default_id not in by_id:
            raise ValueError(f"Unknown default theme ID: {default_id}")
        self._themes = MappingProxyType(by_id)
        self._default_id = default_id

    @classmethod
    def standard(cls) -> "ThemeRegistry":
        root = ResourceLocator.standard().required_directory("app", "themes")
        return cls(
            (
                Theme(
                    "midnight",
                    "Midnight",
                    True,
                    root / "midnight.qss",
                    "#6f7df4",
                    "Near-black navy with a calm indigo accent.",
                ),
                Theme(
                    "forest",
                    "Forest",
                    True,
                    root / "forest.qss",
                    "#63b58d",
                    "Green-charcoal with a muted emerald accent.",
                ),
                Theme(
                    "slate",
                    "Slate",
                    True,
                    root / "slate.qss",
                    "#74a3c7",
                    "Neutral dark gray with a steel-blue accent.",
                ),
                Theme(
                    "warm_neutral",
                    "Warm Neutral",
                    False,
                    root / "warm_neutral.qss",
                    "#a45f45",
                    "Soft cream and taupe with a terracotta accent.",
                ),
                Theme(
                    "light",
                    "Light",
                    False,
                    root / "light.qss",
                    "#3f72d8",
                    "Clean white and light gray with a blue accent.",
                ),
            )
        )

    @property
    def default(self) -> Theme:
        return self._themes[self._default_id]

    @property
    def themes(self) -> tuple[Theme, ...]:
        return tuple(self._themes.values())

    def get(self, theme_id: str) -> Theme:
        try:
            return self._themes[theme_id]
        except KeyError as exc:
            raise KeyError(f"Unknown theme ID: {theme_id}") from exc

    def get_or_default(self, theme_id: str) -> Theme:
        return self._themes.get(theme_id, self.default)
