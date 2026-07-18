"""Stable shortcut action identifiers and immutable metadata."""

from dataclasses import dataclass
from enum import StrEnum

from app.timer.enums import TimerState


class ShortcutActionId(StrEnum):
    PAUSE_RESUME = "pause_resume"
    TOGGLE_FULLSCREEN = "toggle_fullscreen"
    EXIT_FULLSCREEN = "exit_fullscreen"
    STOP_SESSION = "stop_session"
    MARK_DISTRACTION = "mark_distraction"
    TOGGLE_QUOTE = "toggle_quote"
    SHOW_CONTROLS = "show_controls"
    SHOW_SHORTCUT_HELP = "show_shortcut_help"


@dataclass(frozen=True, slots=True)
class ShortcutActionDefinition:
    action_id: ShortcutActionId
    name: str
    description: str
    default_sequence: str
    default_enabled: bool
    allowed_states: frozenset[TimerState]
    confirmation_required: bool = False
