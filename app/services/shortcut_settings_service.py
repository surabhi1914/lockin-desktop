"""Validated, device-local focus shortcut preferences backed only by QSettings."""

import logging

from PySide6.QtCore import QObject, QSettings, Signal

from app.shortcuts.actions import ShortcutActionId
from app.shortcuts.bindings import ShortcutBinding
from app.shortcuts.errors import InvalidShortcutBindingError, ShortcutError
from app.shortcuts.registry import ShortcutRegistry
from app.shortcuts.validator import ShortcutValidator

LOGGER = logging.getLogger(__name__)


class ShortcutSettingsService(QObject):
    """Load and atomically apply one complete validated shortcut set."""

    bindings_changed = Signal(object)
    warning_raised = Signal(str)
    SCHEMA_VERSION = 1

    def __init__(
        self,
        settings: QSettings,
        registry: ShortcutRegistry | None = None,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self.registry = registry or ShortcutRegistry()
        self.validator = ShortcutValidator(self.registry)
        self._warnings: tuple[str, ...] = ()

    @property
    def warnings(self) -> tuple[str, ...]:
        return self._warnings

    @property
    def qsettings(self) -> QSettings:
        return self._settings

    def get(self, action_id: ShortcutActionId | str) -> ShortcutBinding:
        stable_id = self.registry.get(action_id).action_id
        return next(item for item in self.get_all() if item.action_id is stable_id)

    def get_all(self) -> tuple[ShortcutBinding, ...]:
        schema_value = self._settings.value("shortcuts/schema_version")
        migration_needed = schema_value != self.SCHEMA_VERSION
        candidates: dict[ShortcutActionId, ShortcutBinding] = {}
        reset_ids: set[ShortcutActionId] = set()
        warnings: list[str] = []
        for definition in self.registry.definitions:
            enabled = self._read_bool(
                self._enabled_key(definition.action_id), definition.default_enabled
            )
            raw_key = self._settings.value(
                self._key_key(definition.action_id), definition.default_sequence
            )
            key = raw_key if isinstance(raw_key, str) else definition.default_sequence
            try:
                candidates[definition.action_id] = self.validator.make_binding(
                    definition.action_id, key, enabled
                )
            except InvalidShortcutBindingError:
                candidates[definition.action_id] = self.validator.default_binding(
                    definition.action_id
                )
                reset_ids.add(definition.action_id)
                warnings.append(f"Invalid shortcut for {definition.name} was restored to default.")
        while True:
            conflicts = self._conflicting_ids(tuple(candidates.values()))
            if not conflicts:
                break
            newly_reset = conflicts - reset_ids
            for action_id in conflicts:
                candidates[action_id] = self.validator.default_binding(action_id)
                reset_ids.add(action_id)
            names = ", ".join(self.registry.get(item).name for item in sorted(conflicts))
            warnings.append(f"Conflicting stored shortcuts ({names}) were restored to defaults.")
            if not newly_reset:  # pragma: no cover - defaults are unique by registry contract
                raise ShortcutError("Stored shortcut conflicts could not be recovered.")
        result = self.validator.validate_set(
            candidates[definition.action_id] for definition in self.registry.definitions
        )
        self._warnings = tuple(dict.fromkeys(warnings))
        if reset_ids or migration_needed:
            self._persist_recovered(result)
        for warning in self._warnings:
            LOGGER.warning(warning)
            self.warning_raised.emit(warning)
        return result

    def validate(self, bindings: tuple[ShortcutBinding, ...]) -> tuple[ShortcutBinding, ...]:
        return self.validator.validate_set(bindings)

    def save_all(self, bindings: tuple[ShortcutBinding, ...]) -> tuple[ShortcutBinding, ...]:
        validated = self.validator.validate_set(bindings)
        keys = self._all_keys()
        previous = {key: self._settings.value(key) for key in keys}
        existed = {key: self._settings.contains(key) for key in keys}
        try:
            self._write(validated)
            self._settings.sync()
            if self._settings.status() is not QSettings.Status.NoError:
                raise ShortcutError("QSettings could not save focus shortcuts.")
        except Exception:
            for key in keys:
                if existed[key]:
                    self._settings.setValue(key, previous[key])
                else:
                    self._settings.remove(key)
            self._settings.sync()
            raise
        self._warnings = ()
        self.bindings_changed.emit(validated)
        return validated

    def reset_one(self, action_id: ShortcutActionId | str) -> tuple[ShortcutBinding, ...]:
        stable_id = self.registry.get(action_id).action_id
        bindings = tuple(
            self.validator.default_binding(stable_id) if item.action_id is stable_id else item
            for item in self.get_all()
        )
        return self.save_all(bindings)

    def reset_all(self) -> tuple[ShortcutBinding, ...]:
        return self.save_all(
            tuple(
                self.validator.default_binding(definition.action_id)
                for definition in self.registry.definitions
            )
        )

    def _write(self, bindings: tuple[ShortcutBinding, ...]) -> None:
        self._settings.setValue("shortcuts/schema_version", self.SCHEMA_VERSION)
        for binding in bindings:
            self._settings.setValue(self._enabled_key(binding.action_id), binding.enabled)
            self._settings.setValue(self._key_key(binding.action_id), binding.key_sequence)

    def _persist_recovered(self, bindings: tuple[ShortcutBinding, ...]) -> None:
        self._write(bindings)
        self._settings.sync()

    def _conflicting_ids(self, bindings: tuple[ShortcutBinding, ...]) -> set[ShortcutActionId]:
        by_key: dict[str, list[ShortcutActionId]] = {}
        for binding in bindings:
            if binding.enabled:
                by_key.setdefault(binding.key_sequence.casefold(), []).append(binding.action_id)
        return {
            action_id
            for action_ids in by_key.values()
            if len(action_ids) > 1
            for action_id in action_ids
        }

    def _all_keys(self) -> tuple[str, ...]:
        return (
            "shortcuts/schema_version",
            *(
                key
                for definition in self.registry.definitions
                for key in (
                    self._enabled_key(definition.action_id),
                    self._key_key(definition.action_id),
                )
            ),
        )

    @staticmethod
    def _enabled_key(action_id: ShortcutActionId) -> str:
        return f"shortcuts/{action_id.value}/enabled"

    @staticmethod
    def _key_key(action_id: ShortcutActionId) -> str:
        return f"shortcuts/{action_id.value}/key"

    def _read_bool(self, key: str, default: bool) -> bool:
        value = self._settings.value(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in {0, 1}:
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
        return default
