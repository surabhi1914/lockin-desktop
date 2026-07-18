from dataclasses import replace

import pytest

from app.shortcuts.actions import ShortcutActionId
from app.shortcuts.errors import (
    InvalidShortcutBindingError,
    ShortcutConflictError,
    UnknownShortcutActionError,
)
from app.shortcuts.registry import ShortcutRegistry
from app.shortcuts.validator import ShortcutValidator


def test_registry_has_eight_stable_unique_defaults_and_stop_confirmation() -> None:
    registry = ShortcutRegistry()
    assert registry.action_ids == tuple(ShortcutActionId)
    assert len(registry.definitions) == 8
    assert len(set(registry.action_ids)) == 8
    assert [item.default_sequence for item in registry.definitions] == [
        "Space",
        "F11",
        "Esc",
        "Ctrl+Shift+S",
        "D",
        "Q",
        "C",
        "Ctrl+/",
    ]
    assert all(item.default_enabled for item in registry.definitions)
    assert registry.get(ShortcutActionId.STOP_SESSION).confirmation_required
    assert not registry.get(ShortcutActionId.PAUSE_RESUME).confirmation_required
    with pytest.raises(UnknownShortcutActionError):
        registry.get("not_an_action")


def test_validator_normalizes_defaults_and_rejects_unsafe_sequences() -> None:
    registry = ShortcutRegistry()
    validator = ShortcutValidator(registry)
    defaults = tuple(validator.default_binding(item.action_id) for item in registry.definitions)
    assert validator.validate_set(defaults) == defaults
    assert validator.make_binding(ShortcutActionId.PAUSE_RESUME, "ctrl+p", True).key_sequence == (
        "Ctrl+P"
    )
    for value in ("Ctrl", "Ctrl+K, Ctrl+C", "Alt+F4", "Meta+D", "Print Screen", "BogusKey"):
        with pytest.raises(InvalidShortcutBindingError):
            validator.make_binding(ShortcutActionId.PAUSE_RESUME, value, True)
    with pytest.raises(InvalidShortcutBindingError):
        validator.make_binding(ShortcutActionId.PAUSE_RESUME, "", True)
    assert validator.make_binding(ShortcutActionId.PAUSE_RESUME, "", False).key_sequence == ""
    with pytest.raises(InvalidShortcutBindingError):
        validator.make_binding(ShortcutActionId.STOP_SESSION, "S", True)
    assert validator.make_binding(ShortcutActionId.STOP_SESSION, "F9", True).key_sequence == "F9"
    with pytest.raises(InvalidShortcutBindingError):
        validator.validate_set(defaults[:-1])


def test_enabled_conflicts_rejected_but_disabled_duplicates_allowed() -> None:
    registry = ShortcutRegistry()
    validator = ShortcutValidator(registry)
    defaults = [validator.default_binding(item.action_id) for item in registry.definitions]
    defaults[6] = validator.make_binding(ShortcutActionId.SHOW_CONTROLS, "F11", True)
    with pytest.raises(ShortcutConflictError) as caught:
        validator.validate_set(tuple(defaults))
    assert caught.value.first_name == "Toggle full screen"
    assert caught.value.second_name == "Show focus controls"
    defaults[6] = replace(defaults[6], enabled=False)
    validated = validator.validate_set(tuple(defaults))
    assert not validated[6].enabled
    assert validated[6].key_sequence == "F11"
