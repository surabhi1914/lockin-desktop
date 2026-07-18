"""Stable ordered registry for all Phase 5 shortcut actions."""

from types import MappingProxyType

from app.shortcuts.actions import ShortcutActionDefinition, ShortcutActionId
from app.shortcuts.errors import UnknownShortcutActionError
from app.timer.enums import TimerState

_ACTIVE = frozenset(
    {TimerState.RUNNING, TimerState.PAUSED, TimerState.COMPLETED, TimerState.OVERTIME}
)


class ShortcutRegistry:
    """Expose stable definitions in deterministic display order."""

    def __init__(self) -> None:
        definitions = (
            ShortcutActionDefinition(
                ShortcutActionId.PAUSE_RESUME,
                "Pause or resume",
                "Pause running focus or resume a paused session.",
                "Space",
                True,
                frozenset({TimerState.RUNNING, TimerState.PAUSED, TimerState.OVERTIME}),
            ),
            ShortcutActionDefinition(
                ShortcutActionId.TOGGLE_FULLSCREEN,
                "Toggle full screen",
                "Enter or leave full screen without changing the timer.",
                "F11",
                True,
                _ACTIVE,
            ),
            ShortcutActionDefinition(
                ShortcutActionId.EXIT_FULLSCREEN,
                "Exit full screen",
                "Leave full screen only; never stop or exit LockIn.",
                "Esc",
                True,
                _ACTIVE,
            ),
            ShortcutActionDefinition(
                ShortcutActionId.STOP_SESSION,
                "Stop session",
                "Open the existing confirmation before stopping focus.",
                "Ctrl+Shift+S",
                True,
                _ACTIVE,
                confirmation_required=True,
            ),
            ShortcutActionDefinition(
                ShortcutActionId.MARK_DISTRACTION,
                "Mark distraction",
                "Record one in-memory distraction without pausing.",
                "D",
                True,
                frozenset({TimerState.RUNNING, TimerState.OVERTIME}),
            ),
            ShortcutActionDefinition(
                ShortcutActionId.TOGGLE_QUOTE,
                "Show or hide quote",
                "Toggle the same static quote selected for this session.",
                "Q",
                True,
                _ACTIVE,
            ),
            ShortcutActionDefinition(
                ShortcutActionId.SHOW_CONTROLS,
                "Show focus controls",
                "Reveal the focus controls and cursor and restart auto-hide.",
                "C",
                True,
                _ACTIVE,
            ),
            ShortcutActionDefinition(
                ShortcutActionId.SHOW_SHORTCUT_HELP,
                "Shortcut help",
                "Show or close the current local shortcut mapping.",
                "Ctrl+/",
                True,
                _ACTIVE,
            ),
        )
        by_id = {definition.action_id: definition for definition in definitions}
        if len(by_id) != len(definitions):
            raise ValueError("shortcut action IDs must be unique")
        self._definitions = definitions
        self._by_id = MappingProxyType(by_id)

    @property
    def definitions(self) -> tuple[ShortcutActionDefinition, ...]:
        return self._definitions

    @property
    def action_ids(self) -> tuple[ShortcutActionId, ...]:
        return tuple(definition.action_id for definition in self._definitions)

    def get(self, action_id: ShortcutActionId | str) -> ShortcutActionDefinition:
        try:
            stable_id = ShortcutActionId(action_id)
            return self._by_id[stable_id]
        except (KeyError, ValueError) as exc:
            raise UnknownShortcutActionError(str(action_id)) from exc
