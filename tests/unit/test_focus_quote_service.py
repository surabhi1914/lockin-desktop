from collections.abc import Sequence

from app.services.focus_quote_service import FocusQuoteService
from app.services.portable_preview_service import QuotePreview


class FakePreview:
    def __init__(self, quotes: tuple[QuotePreview, ...], *, fail: bool = False) -> None:
        self.quotes = quotes
        self.fail = fail
        self.calls = 0

    def active_quote_count(self) -> int:
        if self.fail:
            raise RuntimeError("bad CSV")
        return len(self.quotes)

    def active_quotes(self, *, limit: int = 5) -> tuple[QuotePreview, ...]:
        self.calls += 1
        return self.quotes[:limit]


def test_static_quote_selection_is_deterministic_and_optional() -> None:
    quotes = (
        QuotePreview("q1", "First", "", ""),
        QuotePreview("q2", "Second", "Author", ""),
    )
    preview = FakePreview(quotes)
    selected: list[Sequence[QuotePreview]] = []
    service = FocusQuoteService(  # type: ignore[arg-type]
        preview,
        selector=lambda values: (selected.append(values), values[1])[1],
    )
    assert service.select_for_session(show_quotes=True) == quotes[1]
    assert len(selected) == 1
    assert service.select_for_session(show_quotes=False) is None
    assert preview.calls == 1


def test_no_quote_or_validation_failure_hides_quote() -> None:
    assert FocusQuoteService(FakePreview(())).select_for_session(show_quotes=True) is None  # type: ignore[arg-type]
    assert (
        FocusQuoteService(FakePreview((), fail=True)).select_for_session(  # type: ignore[arg-type]
            show_quotes=True
        )
        is None
    )
