"""Typed shortcut and distraction failures."""

from app.shortcuts.actions import ShortcutActionId


class ShortcutError(Exception):
    """Base class for configurable shortcut failures."""


class UnknownShortcutActionError(ShortcutError, KeyError):
    """Raised for an action ID outside the stable registry."""


class InvalidShortcutBindingError(ShortcutError, ValueError):
    """Raised when a key sequence is empty, unsafe, or unsupported."""


class ShortcutConflictError(ShortcutError):
    """Raised when two enabled actions have the same normalized sequence."""

    def __init__(
        self,
        key_sequence: str,
        first_action_id: ShortcutActionId,
        second_action_id: ShortcutActionId,
        first_name: str,
        second_name: str,
    ) -> None:
        self.key_sequence = key_sequence
        self.first_action_id = first_action_id
        self.second_action_id = second_action_id
        self.first_name = first_name
        self.second_name = second_name
        super().__init__(
            f'"{key_sequence}" is already assigned to "{first_name}." '
            f'Choose another shortcut for "{second_name}."'
        )


class ShortcutDispatchError(ShortcutError):
    """Raised when an otherwise valid shortcut action cannot run safely."""


class ShortcutContextBlockedError(ShortcutError):
    """Raised when focus, window, modal, or text context blocks dispatch."""


class DistractionMarkerError(ShortcutError):
    """Raised when an in-memory distraction marker cannot be recorded."""
