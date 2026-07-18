"""Small, UI-independent navigation state."""

from collections.abc import Iterable


class UnknownPageError(KeyError):
    """Raised when navigation targets an unregistered page."""


class NavigationState:
    def __init__(self, page_ids: Iterable[str], *, initial_page_id: str = "home") -> None:
        self._page_ids = tuple(page_ids)
        if len(set(self._page_ids)) != len(self._page_ids):
            raise ValueError("Navigation page IDs must be unique")
        if initial_page_id not in self._page_ids:
            raise UnknownPageError(initial_page_id)
        self._current_page_id = initial_page_id

    @property
    def page_ids(self) -> tuple[str, ...]:
        return self._page_ids

    @property
    def current_page_id(self) -> str:
        return self._current_page_id

    def select(self, page_id: str) -> bool:
        if page_id not in self._page_ids:
            raise UnknownPageError(page_id)
        changed = page_id != self._current_page_id
        self._current_page_id = page_id
        return changed
