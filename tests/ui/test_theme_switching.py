from app.ui.pages.settings_page import SettingsPage


def test_all_themes_apply_persist_and_preserve_page(app_context: object) -> None:
    window = app_context.window  # type: ignore[attr-defined]
    service = app_context.theme_service  # type: ignore[attr-defined]
    window.navigate("quotes")
    original_page = window.page("quotes")
    for theme in service.registry.themes:
        applied = service.apply(theme.theme_id)
        app_context.settings.set_theme_id(applied.theme_id)  # type: ignore[attr-defined]
        assert service.current_theme == theme
        assert window.current_page_id == "quotes"
        assert window.page("quotes") is original_page
    assert app_context.settings.theme_id() == "light"  # type: ignore[attr-defined]


def test_settings_selector_applies_theme(app_context: object) -> None:
    page = app_context.window.page("settings")  # type: ignore[attr-defined]
    assert isinstance(page, SettingsPage)
    page.theme_selector.setCurrentIndex(page.theme_selector.findData("forest"))
    assert app_context.theme_service.current_theme.theme_id == "forest"  # type: ignore[attr-defined]
    assert app_context.settings.theme_id() == "forest"  # type: ignore[attr-defined]
