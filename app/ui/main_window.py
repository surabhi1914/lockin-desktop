"""Standard QMainWindow shell, navigation, and geometry persistence."""

from collections.abc import Callable
from pathlib import Path
from types import MappingProxyType

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QCloseEvent, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QWidget,
)

from app.services.settings_service import SettingsService, SidebarStartup
from app.ui.dialogs.about_dialog import AboutDialog
from app.ui.navigation import NavigationState
from app.ui.page_registry import PageRegistry
from app.ui.sidebar import Sidebar

CloseRequestHandler = Callable[[], bool]


class MainWindow(QMainWindow):
    page_changed = Signal(str)

    DEFAULT_WIDTH = 1180
    DEFAULT_HEIGHT = 760
    MINIMUM_WIDTH = 940
    MINIMUM_HEIGHT = 620

    def __init__(self, registry: PageRegistry, settings: SettingsService) -> None:
        super().__init__()
        self._registry = registry
        self._settings = settings
        self._close_request_handler: CloseRequestHandler | None = None
        self._pages: dict[str, QWidget] = {}
        self._stack_indexes: dict[str, int] = {}
        self._geometry_was_restored = False
        self._focus_widget: QWidget | None = None
        self._about_paths: tuple[Path, Path] | None = None
        self.setWindowTitle("LockIn")
        about_action = QAction("About LockIn", self)
        about_action.triggered.connect(self._show_about)
        self.menuBar().addMenu("Help").addAction(about_action)
        self.setMinimumSize(self.MINIMUM_WIDTH, self.MINIMUM_HEIGHT)
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        self.shell_widget = QWidget()
        self.shell_widget.setObjectName("contentRoot")
        shell_layout = QHBoxLayout(self.shell_widget)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        startup = settings.sidebar_startup()
        collapsed = settings.sidebar_collapsed()
        if startup == SidebarStartup.EXPANDED:
            collapsed = False
        elif startup == SidebarStartup.COLLAPSED:
            collapsed = True
        self.sidebar = Sidebar(registry, collapsed=collapsed)
        self.stack = QStackedWidget()
        self.stack.setObjectName("pageStack")
        for definition in registry.definitions:
            page = definition.factory()
            page.setAccessibleName(definition.title)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setWidget(page)
            self._pages[definition.page_id] = page
            self._stack_indexes[definition.page_id] = self.stack.addWidget(scroll)
        shell_layout.addWidget(self.sidebar)
        shell_layout.addWidget(self.stack, 1)
        self.root_stack = QStackedWidget()
        self.root_stack.setObjectName("rootStack")
        self.root_stack.addWidget(self.shell_widget)
        self.setCentralWidget(self.root_stack)

        initial_page = settings.last_page_id()
        self.navigation = NavigationState(registry.page_ids, initial_page_id=initial_page)
        self.sidebar.page_requested.connect(self.navigate)
        self.sidebar.collapsed_changed.connect(self._sidebar_collapsed_changed)
        self.navigate(initial_page)
        self._restore_window_state()

    @property
    def pages(self) -> MappingProxyType[str, QWidget]:
        return MappingProxyType(self._pages)

    @property
    def current_page_id(self) -> str:
        return self.navigation.current_page_id

    def page(self, page_id: str) -> QWidget:
        return self._pages[page_id]

    def set_close_request_handler(self, handler: CloseRequestHandler) -> None:
        self._close_request_handler = handler

    def configure_about(self, runtime_root: Path, portable_root: Path) -> None:
        self._about_paths = (runtime_root, portable_root)

    def _show_about(self) -> None:
        if self._about_paths is None:
            return
        AboutDialog(*self._about_paths, self).exec()

    @property
    def focus_view_active(self) -> bool:
        return (
            self._focus_widget is not None and self.root_stack.currentWidget() is self._focus_widget
        )

    def install_focus_widget(self, widget: QWidget) -> None:
        if self._focus_widget is widget:
            return
        if self._focus_widget is not None:
            self.root_stack.removeWidget(self._focus_widget)
        self._focus_widget = widget
        self.root_stack.addWidget(widget)

    def enter_focus_view(self) -> None:
        if self._focus_widget is None:
            raise RuntimeError("focus experience has not been installed")
        self.root_stack.setCurrentWidget(self._focus_widget)

    def leave_focus_view(self) -> None:
        self.root_stack.setCurrentWidget(self.shell_widget)

    def navigate(self, page_id: str) -> None:
        self.navigation.select(page_id)
        self.stack.setCurrentIndex(self._stack_indexes[page_id])
        self.sidebar.select_page(page_id)
        page = self._pages[page_id]
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()
        self._settings.set_last_page_id(page_id)
        self.page_changed.emit(page_id)

    def save_ui_state(self) -> None:
        self._settings.set_geometry(self.saveGeometry())
        self._settings.set_window_state(self.saveState())
        self._settings.set_last_page_id(self.current_page_id)
        self._settings.set_sidebar_collapsed(self.sidebar.collapsed)

    def recover_on_screen(self) -> None:
        screens = QApplication.screens()
        if not screens:
            return
        frame = self.frameGeometry()
        if any(frame.intersects(screen.availableGeometry()) for screen in screens):
            return
        available = QApplication.primaryScreen().availableGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._close_request_handler is not None and not self._close_request_handler():
            event.ignore()
            return
        event.accept()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.recover_on_screen()

    def _restore_window_state(self) -> None:
        geometry = self._settings.geometry()
        if geometry is not None:
            self._geometry_was_restored = self.restoreGeometry(geometry)
        state = self._settings.window_state()
        if state is not None:
            self.restoreState(state)
        if not self._geometry_was_restored:
            self._center_on_primary_screen()
        self.recover_on_screen()

    def _center_on_primary_screen(self) -> None:
        screen = QApplication.primaryScreen()
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def _sidebar_collapsed_changed(self, collapsed: bool) -> None:
        self._settings.set_sidebar_collapsed(collapsed)
