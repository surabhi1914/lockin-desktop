from unittest.mock import Mock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from app.shortcuts.actions import ShortcutActionId
from app.shortcuts.qt_shortcut_manager import QtShortcutManager
from app.shortcuts.registry import ShortcutRegistry
from app.shortcuts.validator import ShortcutValidator


def test_manager_lifecycle_local_context_refresh_and_no_duplicates(qtbot: object) -> None:
    focus = QWidget()
    qtbot.addWidget(focus)  # type: ignore[attr-defined]
    dispatcher = Mock()
    manager = QtShortcutManager(focus, dispatcher)
    registry = ShortcutRegistry()
    validator = ShortcutValidator(registry)
    defaults = tuple(validator.default_binding(item.action_id) for item in registry.definitions)
    assert not manager.active and manager.shortcut_objects == ()
    manager.activate(defaults)
    assert manager.active and len(manager.shortcut_objects) == 8
    assert all(
        item.context() is Qt.ShortcutContext.WidgetWithChildrenShortcut
        for item in manager.shortcut_objects
    )
    first_objects = manager.shortcut_objects
    manager.activate(defaults)
    assert len(manager.shortcut_objects) == 8
    assert not set(first_objects) & set(manager.shortcut_objects)
    custom = tuple(
        validator.make_binding(item.action_id, item.key_sequence, False)
        if item.action_id is ShortcutActionId.MARK_DISTRACTION
        else item
        for item in defaults
    )
    manager.refresh(custom)
    assert len(manager.shortcut_objects) == 7
    assert all(
        item.action_id is not ShortcutActionId.MARK_DISTRACTION for item in custom if item.enabled
    )
    manager.dispose()
    assert not manager.active and manager.active_bindings == ()
