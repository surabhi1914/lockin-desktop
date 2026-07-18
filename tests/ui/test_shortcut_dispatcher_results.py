from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget

from app.shortcuts.actions import ShortcutActionId
from app.shortcuts.dispatcher import DispatchResult, ShortcutDispatcher
from app.shortcuts.registry import ShortcutRegistry
from app.shortcuts.validator import ShortcutValidator
from app.timer.enums import TimerState


def test_dispatcher_typed_ignored_failed_and_missing_results(
    qapp: QApplication, qtbot: object
) -> None:
    window = QMainWindow()
    focus = QWidget()
    window.setCentralWidget(focus)
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    registry = ShortcutRegistry()
    validator = ShortcutValidator(registry)
    bindings = tuple(validator.default_binding(item.action_id) for item in registry.definitions)
    handler_result = True
    handler_raises = False

    def handler(_action: ShortcutActionId) -> bool:
        if handler_raises:
            raise RuntimeError("dispatch failed")
        return handler_result

    dispatcher = ShortcutDispatcher(
        registry,
        window,
        focus,
        lambda: bindings,
        lambda: True,
        lambda: TimerState.RUNNING,
        lambda: False,
        lambda: False,
        lambda: False,
        handler,
    )
    window.show()
    window.activateWindow()
    focus.setFocus()
    qapp.processEvents()
    assert dispatcher.dispatch("unknown") is DispatchResult.FAILED
    assert dispatcher.last_error
    assert dispatcher.dispatch(ShortcutActionId.EXIT_FULLSCREEN) is DispatchResult.IGNORED
    assert dispatcher.dispatch(ShortcutActionId.TOGGLE_QUOTE) is DispatchResult.IGNORED
    bindings = bindings[:-1]
    assert dispatcher.dispatch(ShortcutActionId.SHOW_SHORTCUT_HELP) is DispatchResult.FAILED
    defaults = tuple(validator.default_binding(item.action_id) for item in registry.definitions)
    for disabled_id in registry.action_ids:
        bindings = tuple(
            validator.make_binding(item.action_id, item.key_sequence, False)
            if item.action_id is disabled_id
            else item
            for item in defaults
        )
        assert dispatcher.dispatch(disabled_id) is DispatchResult.IGNORED
    bindings = defaults
    modal = QDialog(window)
    modal.setModal(True)
    modal.show()
    qapp.processEvents()
    assert QApplication.activeModalWidget() is modal
    assert dispatcher.dispatch(ShortcutActionId.SHOW_CONTROLS) is DispatchResult.BLOCKED
    modal.hide()
    window.activateWindow()
    focus.setFocus()
    qapp.processEvents()
    bindings = tuple(validator.default_binding(item.action_id) for item in registry.definitions)
    handler_result = False
    assert dispatcher.dispatch(ShortcutActionId.SHOW_CONTROLS) is DispatchResult.IGNORED
    handler_raises = True
    assert dispatcher.dispatch(ShortcutActionId.SHOW_CONTROLS) is DispatchResult.FAILED
    assert dispatcher.last_error == "dispatch failed"
