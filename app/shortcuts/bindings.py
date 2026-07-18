"""Immutable shortcut binding values."""

from dataclasses import dataclass

from app.shortcuts.actions import ShortcutActionId


@dataclass(frozen=True, slots=True)
class ShortcutBinding:
    action_id: ShortcutActionId
    key_sequence: str
    enabled: bool
    is_default: bool
    display_text: str
