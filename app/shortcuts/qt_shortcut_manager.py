"""Lifecycle owner for focus-widget-scoped QShortcut objects."""

from functools import partial

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

from app.shortcuts.actions import ShortcutActionId
from app.shortcuts.bindings import ShortcutBinding
from app.shortcuts.dispatcher import ShortcutDispatcher


class QtShortcutManager(QObject):
    """Install only local focus shortcuts and retain every Qt object reference."""

    def __init__(
        self,
        focus_widget: QWidget,
        dispatcher: ShortcutDispatcher,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent or focus_widget)
        self._focus_widget = focus_widget
        self._dispatcher = dispatcher
        self._shortcuts: dict[ShortcutActionId, QShortcut] = {}
        self._active_bindings: tuple[ShortcutBinding, ...] = ()

    @property
    def active(self) -> bool:
        return bool(self._shortcuts)

    @property
    def active_bindings(self) -> tuple[ShortcutBinding, ...]:
        return self._active_bindings

    @property
    def shortcut_objects(self) -> tuple[QShortcut, ...]:
        return tuple(self._shortcuts.values())

    def activate(self, bindings: tuple[ShortcutBinding, ...]) -> None:
        self.deactivate()
        self._active_bindings = bindings
        for binding in bindings:
            if not binding.enabled:
                continue
            shortcut = QShortcut(
                QKeySequence.fromString(
                    binding.key_sequence, QKeySequence.SequenceFormat.PortableText
                ),
                self._focus_widget,
            )
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(partial(self._dispatcher.dispatch, binding.action_id))
            self._shortcuts[binding.action_id] = shortcut

    def refresh(self, bindings: tuple[ShortcutBinding, ...]) -> None:
        if self.active:
            self.activate(bindings)
        else:
            self._active_bindings = ()

    def deactivate(self) -> None:
        for shortcut in self._shortcuts.values():
            shortcut.setEnabled(False)
            shortcut.setParent(None)
            shortcut.deleteLater()
        self._shortcuts.clear()
        self._active_bindings = ()

    def dispose(self) -> None:
        self.deactivate()
