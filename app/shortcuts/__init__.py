"""Configurable, focus-local shortcut contracts and Qt integration."""

from app.shortcuts.actions import ShortcutActionDefinition, ShortcutActionId
from app.shortcuts.bindings import ShortcutBinding
from app.shortcuts.dispatcher import DispatchResult, ShortcutDispatcher
from app.shortcuts.registry import ShortcutRegistry

__all__ = [
    "DispatchResult",
    "ShortcutActionDefinition",
    "ShortcutActionId",
    "ShortcutBinding",
    "ShortcutDispatcher",
    "ShortcutRegistry",
]
