import pytest
from PySide6.QtWidgets import QApplication, QWidget

from app.ui.navigation import UnknownPageError
from app.ui.page_registry import PageDefinition, PageRegistry


def _definition(page_id: str, order: int) -> PageDefinition:
    return PageDefinition(page_id, page_id.title(), "Description", order, "X", QWidget)


def test_registry_orders_and_creates_pages(qapp: QApplication) -> None:
    registry = PageRegistry((_definition("second", 2), _definition("first", 1)))
    assert registry.page_ids == ("first", "second")
    assert registry.get("first").title == "First"
    assert isinstance(registry.create("first"), QWidget)


def test_registry_rejects_duplicate_and_unknown_ids(qapp: QApplication) -> None:
    with pytest.raises(ValueError, match="Duplicate page ID"):
        PageRegistry((_definition("same", 1), _definition("same", 2)))
    with pytest.raises(ValueError, match="Duplicate page order"):
        PageRegistry((_definition("one", 1), _definition("two", 1)))
    registry = PageRegistry((_definition("home", 0),))
    with pytest.raises(UnknownPageError):
        registry.get("missing")
