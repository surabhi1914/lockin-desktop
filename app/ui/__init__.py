"""Phase 1 desktop-shell widgets and pages."""

from app.ui.navigation import NavigationState, UnknownPageError
from app.ui.page_registry import PageDefinition, PageRegistry

__all__ = ["NavigationState", "PageDefinition", "PageRegistry", "UnknownPageError"]
