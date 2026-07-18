from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QMainWindow

from app.services.focus_window_service import FocusWindowService


class FakeScreen:
    def __init__(self, geometry: QRect) -> None:
        self._geometry = geometry

    def geometry(self) -> QRect:
        return self._geometry

    def availableGeometry(self) -> QRect:
        return self._geometry


def test_current_screen_uses_largest_frame_intersection(qapp: QApplication, qtbot: object) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.setGeometry(800, 100, 800, 600)
    left = FakeScreen(QRect(0, 0, 1000, 900))
    right = FakeScreen(QRect(1000, 0, 1000, 900))
    service = FocusWindowService(  # type: ignore[arg-type]
        window,
        screen_provider=lambda: (left, right),
        primary_screen_provider=lambda: left,
    )
    assert service.choose_current_screen() is right


def test_full_screen_round_trip_has_no_kiosk_or_always_on_top(
    qapp: QApplication, qtbot: object
) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.setGeometry(50, 60, 700, 500)
    window.show()
    original = window.geometry()
    service = FocusWindowService(window)
    assert service.enter_full_screen()
    assert service.is_full_screen
    assert not bool(window.windowFlags() & window.windowFlags().WindowStaysOnTopHint)
    service.exit_full_screen()
    assert not service.is_full_screen
    assert window.geometry().size() == original.size()


def test_full_screen_failure_without_any_screen_is_safe(qapp: QApplication, qtbot: object) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    service = FocusWindowService(
        window,
        screen_provider=lambda: (),
        primary_screen_provider=lambda: None,
    )
    assert not service.enter_full_screen()
    assert not service.is_full_screen
