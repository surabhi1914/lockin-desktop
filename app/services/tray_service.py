"""Gracefully degrading Phase 1 system-tray foundation."""

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMainWindow, QMenu, QSystemTrayIcon


class TrayService(QObject):
    def __init__(
        self,
        window: QMainWindow,
        *,
        available_override: bool | None = None,
        exit_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._available = (
            QSystemTrayIcon.isSystemTrayAvailable()
            if available_override is None
            else available_override
        )
        self._exit_callback = exit_callback or (lambda: None)
        self._first_hide_message_shown = False
        self._focus_status: str | None = None
        self.tray_icon: QSystemTrayIcon | None = None
        self.menu: QMenu | None = None
        self.show_action: QAction | None = None
        self.hide_action: QAction | None = None
        self.exit_action: QAction | None = None
        if self._available:
            self._create_tray()

    @property
    def available(self) -> bool:
        return self._available and self.tray_icon is not None

    def set_exit_callback(self, callback: Callable[[], None]) -> None:
        self._exit_callback = callback

    def show_window(self) -> None:
        if self._window.isFullScreen():
            self._window.showFullScreen()
        elif self._window.isMinimized():
            self._window.showNormal()
        else:
            self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def hide_window(self, *, inform_once: bool = False) -> None:
        self._window.hide()
        if inform_once and self.available and not self._first_hide_message_shown:
            assert self.tray_icon is not None
            self.tray_icon.showMessage(
                "LockIn is still running",
                "Use the tray menu to show LockIn or exit.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            self._first_hide_message_shown = True

    def request_exit(self) -> None:
        self._exit_callback()

    @property
    def focus_status(self) -> str | None:
        return self._focus_status

    def set_focus_status(self, status: str) -> None:
        self._focus_status = status
        if self.tray_icon is not None:
            self.tray_icon.setToolTip(status)

    def clear_focus_status(self) -> None:
        self._focus_status = None
        if self.tray_icon is not None:
            self.tray_icon.setToolTip("LockIn")

    def dispose(self) -> None:
        if self.tray_icon is not None:
            self.tray_icon.hide()
            self.tray_icon.deleteLater()
            self.tray_icon = None
        self._available = False

    def _create_tray(self) -> None:
        self.menu = QMenu()
        self.show_action = self.menu.addAction("Show LockIn")
        self.hide_action = self.menu.addAction("Hide LockIn")
        self.menu.addSeparator()
        self.exit_action = self.menu.addAction("Exit")
        self.show_action.triggered.connect(self.show_window)
        self.hide_action.triggered.connect(self.hide_window)
        self.exit_action.triggered.connect(self.request_exit)
        self.tray_icon = QSystemTrayIcon(self._generated_icon(), self)
        self.tray_icon.setToolTip("LockIn")
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self._activated)
        self.tray_icon.show()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    @staticmethod
    def _generated_icon() -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#5667dc"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(2, 2, 28, 28, 7, 7)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "L")
        painter.end()
        return QIcon(pixmap)
