"""Nonrepeating, injectable quote cycle with gentle favorite weighting."""

from collections.abc import Callable, Sequence
from random import SystemRandom

from app.services.portable_preview_service import QuotePreview

QuoteSelector = Callable[[Sequence[QuotePreview]], QuotePreview]


class QuoteCycle:
    def __init__(
        self,
        quotes: Sequence[QuotePreview],
        *,
        selector: QuoteSelector | None = None,
    ) -> None:
        self._all = tuple(quote for quote in quotes if quote.is_active)
        self._remaining = list(self._all)
        self._selector = selector or SystemRandom().choice
        self._last_id: str | None = None

    def next(self) -> QuotePreview | None:
        if not self._all:
            return None
        if not self._remaining:
            self._remaining = list(self._all)
        eligible = [quote for quote in self._remaining if quote.quote_id != self._last_id]
        if not eligible:
            eligible = list(self._remaining)
        weighted = [quote for quote in eligible for _ in range(2 if quote.is_favorite else 1)]
        selected = self._selector(weighted)
        self._remaining = [
            quote for quote in self._remaining if quote.quote_id != selected.quote_id
        ]
        self._last_id = selected.quote_id
        return selected
