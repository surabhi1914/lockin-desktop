"""Typed metadata for a stylesheet theme."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Theme:
    theme_id: str
    display_name: str
    is_dark: bool
    stylesheet_path: Path
    accent_color: str
    description: str
