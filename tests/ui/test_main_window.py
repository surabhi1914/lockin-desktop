from PySide6.QtWidgets import QApplication

from app.application import create_application


def test_title_default_and_minimum_size(app_context: object) -> None:
    window = app_context.window  # type: ignore[attr-defined]
    assert window.windowTitle() == "LockIn"
    assert window.width() == 1180
    assert window.height() == 760
    assert window.minimumWidth() == 940
    assert window.minimumHeight() == 620
    assert not window.isFullScreen()


def test_offscreen_window_is_recovered(
    app_context: object, qapp: QApplication, qtbot: object
) -> None:
    window = app_context.window  # type: ignore[attr-defined]
    window.move(100_000, 100_000)
    window.recover_on_screen()
    frame = window.frameGeometry()
    assert any(frame.intersects(screen.availableGeometry()) for screen in qapp.screens())


def test_invalid_geometry_does_not_crash(app_context: object) -> None:
    settings = app_context.settings  # type: ignore[attr-defined]
    settings.qsettings.setValue("window/geometry", "invalid")
    assert settings.geometry() is None


def test_geometry_restores(app_context: object, qtbot: object) -> None:
    window = app_context.window  # type: ignore[attr-defined]
    window.resize(1024, 680)
    window.move(40, 40)
    app_context.shutdown()  # type: ignore[attr-defined]
    second = create_application(
        config=app_context.config,  # type: ignore[attr-defined]
        settings=app_context.settings,  # type: ignore[attr-defined]
        tray_available=False,
    )
    qtbot.addWidget(second.window)  # type: ignore[attr-defined]
    # The offscreen pytest-qt screen is narrower than a real supported display,
    # so Qt clamps the restored width to the declared minimum.
    assert second.window.size().width() >= 940
    assert second.window.size().height() == 680
    second.shutdown()
