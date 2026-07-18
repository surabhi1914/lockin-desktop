"""Portable Qt key-sequence normalization and binding-set validation."""

from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from app.shortcuts.actions import ShortcutActionId
from app.shortcuts.bindings import ShortcutBinding
from app.shortcuts.errors import InvalidShortcutBindingError, ShortcutConflictError
from app.shortcuts.registry import ShortcutRegistry


class ShortcutValidator:
    def __init__(self, registry: ShortcutRegistry) -> None:
        self._registry = registry

    def make_binding(
        self,
        action_id: ShortcutActionId | str,
        key_sequence: str,
        enabled: bool,
    ) -> ShortcutBinding:
        definition = self._registry.get(action_id)
        normalized = self.normalize(key_sequence, enabled=enabled, action_id=definition.action_id)
        native = QKeySequence.fromString(
            normalized, QKeySequence.SequenceFormat.PortableText
        ).toString(QKeySequence.SequenceFormat.NativeText)
        return ShortcutBinding(
            definition.action_id,
            normalized,
            enabled,
            enabled == definition.default_enabled and normalized == definition.default_sequence,
            native,
        )

    def default_binding(self, action_id: ShortcutActionId | str) -> ShortcutBinding:
        definition = self._registry.get(action_id)
        return self.make_binding(
            definition.action_id,
            definition.default_sequence,
            definition.default_enabled,
        )

    def normalize(
        self,
        key_sequence: str,
        *,
        enabled: bool,
        action_id: ShortcutActionId | str,
    ) -> str:
        definition = self._registry.get(action_id)
        raw = key_sequence.strip()
        if not raw:
            if enabled:
                raise InvalidShortcutBindingError(
                    f"{definition.name} needs a shortcut while it is enabled."
                )
            return ""
        sequence = QKeySequence.fromString(raw, QKeySequence.SequenceFormat.PortableText)
        portable = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        if sequence.count() != 1 or not portable:
            if sequence.count() > 1 or "," in raw:
                raise InvalidShortcutBindingError("Multi-step shortcut chords are not supported.")
            raise InvalidShortcutBindingError(f'"{raw}" is not a valid shortcut.')
        combination = sequence[0]  # type: ignore[index]
        key = combination.key()
        modifiers = combination.keyboardModifiers()
        if key in {
            Qt.Key.Key_unknown,
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        }:
            raise InvalidShortcutBindingError("A modifier key cannot be used by itself.")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            raise InvalidShortcutBindingError("Windows-key shortcuts are not supported.")
        if key == Qt.Key.Key_Print:
            raise InvalidShortcutBindingError("Print Screen shortcuts are not supported.")
        if portable.casefold() == "alt+f4":
            raise InvalidShortcutBindingError("Alt+F4 cannot be assigned to a focus action.")
        if definition.action_id is ShortcutActionId.STOP_SESSION:
            has_modifier = bool(
                modifiers
                & (
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.AltModifier
                    | Qt.KeyboardModifier.ShiftModifier
                )
            )
            is_function_key = Qt.Key.Key_F1 <= key <= Qt.Key.Key_F35
            if not has_modifier and not is_function_key:
                raise InvalidShortcutBindingError(
                    "Stop session must use a modifier or a function key."
                )
        return portable

    def validate_set(self, bindings: Iterable[ShortcutBinding]) -> tuple[ShortcutBinding, ...]:
        by_id = {binding.action_id: binding for binding in bindings}
        if set(by_id) != set(self._registry.action_ids):
            missing = set(self._registry.action_ids) - set(by_id)
            extra = set(by_id) - set(self._registry.action_ids)
            raise InvalidShortcutBindingError(
                f"Shortcut set has missing actions {sorted(missing)} and extras {sorted(extra)}."
            )
        normalized = tuple(
            self.make_binding(
                definition.action_id,
                by_id[definition.action_id].key_sequence,
                by_id[definition.action_id].enabled,
            )
            for definition in self._registry.definitions
        )
        enabled_by_key: dict[str, ShortcutBinding] = {}
        for binding in normalized:
            if not binding.enabled:
                continue
            earlier = enabled_by_key.get(binding.key_sequence.casefold())
            if earlier is not None:
                first = self._registry.get(earlier.action_id)
                second = self._registry.get(binding.action_id)
                raise ShortcutConflictError(
                    binding.display_text,
                    earlier.action_id,
                    binding.action_id,
                    first.name,
                    second.name,
                )
            enabled_by_key[binding.key_sequence.casefold()] = binding
        return normalized
