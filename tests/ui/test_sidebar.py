from PySide6.QtWidgets import QApplication

from app.application import create_application


def test_sidebar_collapse_expand_tooltips_and_persistence(
    app_context: object, qapp: QApplication, qtbot: object
) -> None:
    window = app_context.window  # type: ignore[attr-defined]
    sidebar = window.sidebar
    assert sidebar.width() == 230
    sidebar.toggle_collapsed()
    assert sidebar.collapsed
    assert sidebar.width() == 72
    assert sidebar.button_for("quotes").toolTip() == "Quotes"
    assert app_context.settings.sidebar_collapsed()  # type: ignore[attr-defined]
    sidebar.toggle_collapsed()
    assert not sidebar.collapsed
    assert sidebar.button_for("quotes").toolTip() == ""
    sidebar.set_collapsed(True)
    app_context.shutdown()  # type: ignore[attr-defined]

    second = create_application(
        config=app_context.config,  # type: ignore[attr-defined]
        settings=app_context.settings,  # type: ignore[attr-defined]
        tray_available=False,
    )
    qtbot.addWidget(second.window)  # type: ignore[attr-defined]
    assert second.window.sidebar.collapsed
    second.shutdown()


def test_selected_navigation_is_clear(app_context: object) -> None:
    sidebar = app_context.window.sidebar  # type: ignore[attr-defined]
    sidebar.select_page("categories")
    assert sidebar.button_for("categories").isChecked()
    assert not sidebar.button_for("home").isChecked()
