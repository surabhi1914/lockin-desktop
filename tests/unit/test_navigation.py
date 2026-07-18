import pytest

from app.ui.navigation import NavigationState, UnknownPageError


def test_navigation_selects_known_pages() -> None:
    navigation = NavigationState(("home", "quotes", "settings"))
    assert navigation.current_page_id == "home"
    assert navigation.select("quotes")
    assert navigation.current_page_id == "quotes"
    assert not navigation.select("quotes")
    assert navigation.page_ids == ("home", "quotes", "settings")


def test_navigation_rejects_duplicates_and_unknown_pages() -> None:
    with pytest.raises(ValueError, match="unique"):
        NavigationState(("home", "home"))
    with pytest.raises(UnknownPageError):
        NavigationState(("home",), initial_page_id="unknown")
    navigation = NavigationState(("home",))
    with pytest.raises(UnknownPageError):
        navigation.select("unknown")
