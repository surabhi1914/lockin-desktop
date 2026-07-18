"""Select one validated local quote for an in-memory focus session."""

from app.quotes.quote_cycle import QuoteCycle, QuoteSelector
from app.services.portable_preview_service import PortablePreviewService, QuotePreview


class FocusQuoteService:
    """Choose one active quote without changing or retaining portable data."""

    def __init__(
        self,
        preview_service: PortablePreviewService,
        *,
        selector: QuoteSelector | None = None,
    ) -> None:
        self._preview_service = preview_service
        self._selector = selector
        self._cycle: QuoteCycle | None = None
        self._completed_hours = 0
        self._current: QuotePreview | None = None

    def select_for_session(self, *, show_quotes: bool) -> QuotePreview | None:
        if not show_quotes:
            return None
        try:
            count = self._preview_service.active_quote_count()
            quotes = self._preview_service.active_quotes(limit=count)
        except (OSError, RuntimeError, ValueError):
            return None
        if not quotes:
            return None
        try:
            self._cycle = QuoteCycle(quotes, selector=self._selector)
            self._completed_hours = 0
            self._current = self._cycle.next()
            return self._current
        except (IndexError, LookupError, ValueError):
            self._cycle = None
            self._current = None
            return None

    def quote_for_focus(self, total_focus_seconds: int) -> QuotePreview | None:
        """Advance once per crossed active-focus hour, including overtime."""
        target_hours = max(0, total_focus_seconds) // 3600
        if self._cycle is None:
            return self._current
        while self._completed_hours < target_hours:
            self._current = self._cycle.next()
            self._completed_hours += 1
        return self._current
