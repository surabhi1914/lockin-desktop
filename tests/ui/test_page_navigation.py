from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.application import create_application
from app.services.settings_service import SettingsService
from app.ui.pages.categories_page import CategoriesPage
from app.ui.pages.home_page import HomePage
from app.ui.pages.quotes_page import QuotesPage
from app.ui.widgets.empty_state import EmptyState


def test_every_required_page_navigates_without_recreation(app_context: object) -> None:
    window = app_context.window  # type: ignore[attr-defined]
    expected = (
        "home",
        "focus_setup",
        "statistics",
        "history",
        "categories",
        "quotes",
        "settings",
    )
    assert app_context.page_registry.page_ids == expected  # type: ignore[attr-defined]
    original = dict(window.pages)
    for page_id in expected:
        window.navigate(page_id)
        assert window.current_page_id == page_id
        assert window.page(page_id) is original[page_id]


def test_last_page_restores_and_invalid_page_falls_back(
    app_context: object, qapp: QApplication, qtbot: object, tmp_path: object
) -> None:
    app_context.window.navigate("quotes")  # type: ignore[attr-defined]
    app_context.shutdown()  # type: ignore[attr-defined]
    second = create_application(
        config=app_context.config,  # type: ignore[attr-defined]
        settings=app_context.settings,  # type: ignore[attr-defined]
        tray_available=False,
    )
    qtbot.addWidget(second.window)  # type: ignore[attr-defined]
    assert second.window.current_page_id == "quotes"
    second.shutdown()

    invalid_settings = SettingsService(
        QSettings(str(tmp_path / "invalid-page.ini"), QSettings.Format.IniFormat)  # type: ignore[operator]
    )
    invalid_settings.qsettings.setValue("navigation/last_page", "not-a-page")
    third = create_application(
        config=app_context.config,  # type: ignore[attr-defined]
        settings=invalid_settings,
        tray_available=False,
    )
    qtbot.addWidget(third.window)  # type: ignore[attr-defined]
    assert third.window.current_page_id == "home"
    third.shutdown()


def test_read_only_previews_and_honest_home_placeholders(app_context: object) -> None:
    categories = app_context.window.page("categories")  # type: ignore[attr-defined]
    quotes = app_context.window.page("quotes")  # type: ignore[attr-defined]
    home = app_context.window.page("home")  # type: ignore[attr-defined]
    assert isinstance(categories, CategoriesPage)
    assert isinstance(quotes, QuotesPage)
    assert isinstance(home, HomePage)
    assert len(categories.category_rows) == 9
    assert len(quotes.quote_rows) >= 40
    assert home.metric_cards[0].value.text() == "00:00"
    assert home.empty_state.isVisibleTo(home) or not home.isVisible()
    assert home.save_goal_button.isEnabled()


def test_zero_data_pages_show_intentional_empty_states(qtbot: object) -> None:
    class EmptyPreview:
        def active_quote_count(self) -> int:
            return 0

        def active_quotes(self, *, limit: int = 5) -> tuple[()]:
            return ()

    preview = EmptyPreview()
    quotes = QuotesPage(preview)  # type: ignore[arg-type]
    qtbot.addWidget(quotes)  # type: ignore[attr-defined]
    assert quotes.findChild(EmptyState) is not None
