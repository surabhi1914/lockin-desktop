"""Defensive focus-local shortcut dispatch with typed outcomes."""

from collections.abc import Callable
from enum import StrEnum

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from app.shortcuts.actions import ShortcutActionId
from app.shortcuts.bindings import ShortcutBinding
from app.shortcuts.registry import ShortcutRegistry
from app.shortcuts.text_input import is_editable_text_widget
from app.timer.enums import TimerState

BindingProvider = Callable[[], tuple[ShortcutBinding, ...]]
ActionHandler = Callable[[ShortcutActionId], bool]
BooleanProvider = Callable[[], bool]
StateProvider = Callable[[], TimerState | None]


class DispatchResult(StrEnum):
    HANDLED = "handled"
    IGNORED = "ignored"
    BLOCKED = "blocked"
    FAILED = "failed"


class ShortcutDispatcher:
    """Recheck all context after Qt reports a local shortcut activation."""

    def __init__(
        self,
        registry: ShortcutRegistry,
        window: QMainWindow,
        focus_widget: QWidget,
        binding_provider: BindingProvider,
        focus_active: BooleanProvider,
        state_provider: StateProvider,
        full_screen_provider: BooleanProvider,
        quote_available_provider: BooleanProvider,
        help_visible_provider: BooleanProvider,
        handler: ActionHandler,
    ) -> None:
        self._registry = registry
        self._window = window
        self._focus_widget = focus_widget
        self._binding_provider = binding_provider
        self._focus_active = focus_active
        self._state_provider = state_provider
        self._full_screen_provider = full_screen_provider
        self._quote_available_provider = quote_available_provider
        self._help_visible_provider = help_visible_provider
        self._handler = handler
        self._last_error: str | None = None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def dispatch(self, action_id: ShortcutActionId | str) -> DispatchResult:
        self._last_error = None
        try:
            definition = self._registry.get(action_id)
        except KeyError as exc:
            self._last_error = str(exc)
            return DispatchResult.FAILED
        binding = next(
            (item for item in self._binding_provider() if item.action_id is definition.action_id),
            None,
        )
        if binding is None:
            self._last_error = f"Missing binding for {definition.action_id.value}."
            return DispatchResult.FAILED
        if not binding.enabled:
            return DispatchResult.IGNORED
        if not self._context_is_active():
            return DispatchResult.BLOCKED
        if QApplication.activeModalWidget() is not None:
            return DispatchResult.BLOCKED
        if self._help_visible_provider():
            if definition.action_id is not ShortcutActionId.SHOW_SHORTCUT_HELP:
                return DispatchResult.BLOCKED
        elif is_editable_text_widget(QApplication.focusWidget()):
            return DispatchResult.BLOCKED
        state = self._state_provider()
        if state is None or state not in definition.allowed_states:
            return DispatchResult.BLOCKED
        if (
            definition.action_id is ShortcutActionId.EXIT_FULLSCREEN
            and not self._full_screen_provider()
        ):
            return DispatchResult.IGNORED
        if (
            definition.action_id is ShortcutActionId.TOGGLE_QUOTE
            and not self._quote_available_provider()
        ):
            return DispatchResult.IGNORED
        try:
            handled = self._handler(definition.action_id)
        except Exception as exc:  # pragma: no cover - final UI safety boundary
            self._last_error = str(exc)
            return DispatchResult.FAILED
        return DispatchResult.HANDLED if handled else DispatchResult.IGNORED

    def _context_is_active(self) -> bool:
        active_window = QApplication.activeWindow()
        return (
            self._focus_active()
            and self._window.isVisible()
            and not self._window.isMinimized()
            and self._focus_widget.isVisibleTo(self._window)
            and self._window.isActiveWindow()
            and active_window is self._window
        )
