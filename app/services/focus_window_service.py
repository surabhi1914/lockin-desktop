"""Window-state and current-monitor policy for the Phase 4 focus experience."""

from collections.abc import Callable, Sequence

from PySide6.QtCore import QByteArray, QObject, QRect, Signal
from PySide6.QtGui import QGuiApplication, QScreen
from PySide6.QtWidgets import QMainWindow

ScreenProvider = Callable[[], Sequence[QScreen]]
PrimaryScreenProvider = Callable[[], QScreen | None]


class FocusWindowService(QObject):
    """Enter full screen on the current window monitor and recover safely."""

    recovered_to_primary = Signal()
    window_error = Signal(str)

    def __init__(
        self,
        window: QMainWindow,
        *,
        screen_provider: ScreenProvider | None = None,
        primary_screen_provider: PrimaryScreenProvider | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent or window)
        self._window = window
        self._screen_provider = screen_provider or QGuiApplication.screens
        self._primary_screen_provider = primary_screen_provider or QGuiApplication.primaryScreen
        self._saved_geometry: QByteArray | None = None
        self._was_maximized = False
        self._is_full_screen = False
        self._target_screen: QScreen | None = None
        application = QGuiApplication.instance()
        if isinstance(application, QGuiApplication):
            application.screenRemoved.connect(self.handle_screen_removed)

    @property
    def is_full_screen(self) -> bool:
        return self._is_full_screen

    @property
    def target_screen(self) -> QScreen | None:
        return self._target_screen

    def choose_current_screen(self) -> QScreen | None:
        screens = tuple(self._screen_provider())
        frame = self._window.frameGeometry()
        best: QScreen | None = None
        best_area = 0
        for screen in screens:
            intersection = frame.intersected(screen.geometry())
            area = max(0, intersection.width()) * max(0, intersection.height())
            if area > best_area:
                best = screen
                best_area = area
        if best is not None:
            return best
        handle = self._window.windowHandle()
        if handle is not None and handle.screen() is not None:
            return handle.screen()
        return self._primary_screen_provider()

    def enter_full_screen(self) -> bool:
        if self._is_full_screen:
            return True
        target = self.choose_current_screen()
        if target is None:
            self.window_error.emit("No screen is available; focus will continue windowed.")
            return False
        self._saved_geometry = self._window.saveGeometry()
        self._was_maximized = self._window.isMaximized()
        try:
            handle = self._window.windowHandle()
            if handle is not None:
                handle.setScreen(target)
            self._window.setGeometry(target.geometry())
            self._window.showFullScreen()
        except RuntimeError as exc:
            self.window_error.emit(f"Could not enter full screen: {exc}")
            self._restore_saved_window()
            return False
        self._target_screen = target
        self._is_full_screen = True
        return True

    def exit_full_screen(self) -> None:
        if not self._is_full_screen:
            return
        self._restore_saved_window()
        self._is_full_screen = False
        self._target_screen = None

    def restore_before_shell(self) -> None:
        """Leave full screen before restoring normal application chrome."""
        self.exit_full_screen()

    def handle_screen_removed(self, removed: QScreen) -> None:
        screens = tuple(self._screen_provider())
        frame_visible = any(
            self._window.frameGeometry().intersects(item.geometry()) for item in screens
        )
        if removed is not self._target_screen and frame_visible:
            return
        primary = self._primary_screen_provider()
        if primary is None:
            self.window_error.emit(
                "The focus monitor was removed and no primary screen is available."
            )
            return
        try:
            if self._is_full_screen:
                self._window.showNormal()
            self._is_full_screen = False
            self._target_screen = None
            self._move_to_available(primary.availableGeometry())
            self._saved_geometry = self._window.saveGeometry()
            self._was_maximized = False
            self._window.show()
            self._window.raise_()
        except RuntimeError as exc:
            self.window_error.emit(f"Could not recover from monitor removal: {exc}")
            return
        self.recovered_to_primary.emit()

    def _restore_saved_window(self) -> None:
        self._window.showNormal()
        if self._saved_geometry is not None:
            self._window.restoreGeometry(self._saved_geometry)
        if self._was_maximized:
            self._window.showMaximized()
        else:
            self._window.showNormal()

    def _move_to_available(self, available: QRect) -> None:
        width = min(max(self._window.minimumWidth(), self._window.width()), available.width())
        height = min(max(self._window.minimumHeight(), self._window.height()), available.height())
        geometry = QRect(0, 0, width, height)
        geometry.moveCenter(available.center())
        self._window.setGeometry(geometry)
