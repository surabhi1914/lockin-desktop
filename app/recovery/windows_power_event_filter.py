"""Isolated Windows WM_POWERBROADCAST adapter with a safe non-Windows fallback."""

import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray
from PySide6.QtWidgets import QApplication

from app.recovery.sleep_detector import PowerEvent, PowerEventSource

WM_POWERBROADCAST = 0x0218
PBT_APMSUSPEND = 0x0004
PBT_APMRESUMESUSPEND = 0x0007
PBT_APMRESUMEAUTOMATIC = 0x0012


class WindowsPowerEventFilter(QAbstractNativeEventFilter):
    def __init__(self, source: PowerEventSource) -> None:
        super().__init__()
        self.source = source
        self.enabled = sys.platform == "win32"
        self._application: QApplication | None = None

    def install(self, application: QApplication) -> None:
        self._application = application
        if self.enabled:
            application.installNativeEventFilter(self)

    def dispose(self) -> None:
        if self.enabled and self._application is not None:
            self._application.removeNativeEventFilter(self)
        self._application = None

    def nativeEventFilter(
        self,
        event_type: QByteArray | bytes | bytearray | memoryview,
        message: int,
    ) -> tuple[bool, int]:
        del event_type
        if not self.enabled or not message:
            return False, 0
        try:
            native = wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError, OSError):
            return False, 0
        if native.message != WM_POWERBROADCAST:
            return False, 0
        event = _power_event(int(native.wParam))
        if event is not None:
            self.source.emit_event(event)
        return False, 0


def _power_event(value: int) -> PowerEvent | None:
    if value == PBT_APMSUSPEND:
        return PowerEvent.SUSPEND
    if value == PBT_APMRESUMEAUTOMATIC:
        return PowerEvent.RESUME_AUTOMATIC
    if value == PBT_APMRESUMESUSPEND:
        return PowerEvent.RESUME_USER
    return None
