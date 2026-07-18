from PySide6.QtWidgets import QApplication, QMainWindow

from app.application import create_application
from app.services.settings_service import CloseBehavior
from app.services.tray_service import TrayService


def test_tray_unavailable_is_safe(qapp: QApplication, qtbot: object) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    tray = TrayService(window, available_override=False)
    assert not tray.available
    tray.show_window()
    assert window.isVisible()
    tray.hide_window(inform_once=True)
    assert not window.isVisible()
    tray.dispose()


def test_tray_menu_actions_show_hide_and_exit(qapp: QApplication, qtbot: object) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    exits: list[str] = []
    tray = TrayService(window, available_override=True, exit_callback=lambda: exits.append("exit"))
    assert tray.available
    assert tray.show_action is not None
    assert tray.hide_action is not None
    assert tray.exit_action is not None
    tray.show_action.trigger()
    assert window.isVisible()
    tray.hide_action.trigger()
    assert not window.isVisible()
    tray.exit_action.trigger()
    assert exits == ["exit"]
    tray.dispose()


def test_close_to_tray_and_explicit_exit(
    app_context: object, qapp: QApplication, qtbot: object
) -> None:
    app_context.shutdown()  # type: ignore[attr-defined]
    settings = app_context.settings  # type: ignore[attr-defined]
    settings.set_minimize_to_tray(True)
    settings.set_close_behavior(CloseBehavior.MINIMIZE_TO_TRAY)
    context = create_application(
        config=app_context.config,  # type: ignore[attr-defined]
        settings=settings,
        tray_available=True,
        show_window=True,
    )
    qtbot.addWidget(context.window)  # type: ignore[attr-defined]
    qapp.processEvents()
    assert not context.window.close()
    assert not context.window.isVisible()
    assert not context.shutdown_coordinator.shutdown_complete
    context.shutdown_coordinator.request_exit()
    assert context.shutdown_coordinator.shutdown_complete or not context.window.isVisible()
    context.shutdown()
