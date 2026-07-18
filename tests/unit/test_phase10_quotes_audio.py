import csv
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from app.audio.completion_sound import CompletionSoundService
from app.portability.csv_contracts import header_for
from app.quotes.quote_cycle import QuoteCycle
from app.quotes.quote_store import QuoteRecord, QuoteStore
from app.services.focus_quote_service import FocusQuoteService
from app.services.portable_preview_service import QuotePreview
from app.services.settings_service import SettingsService


class Preview:
    def __init__(self, quotes: tuple[QuotePreview, ...]) -> None:
        self.quotes = quotes

    def active_quote_count(self) -> int:
        return len(self.quotes)

    def active_quotes(self, *, limit: int = 5) -> tuple[QuotePreview, ...]:
        return self.quotes[:limit]


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, float]] = []

    def play(self, asset: Path, volume: float) -> None:
        self.calls.append((asset, volume))


def _quotes() -> tuple[QuotePreview, ...]:
    return (
        QuotePreview("q1", "One", "", "focus"),
        QuotePreview("q2", "Two", "", "focus", True),
        QuotePreview("q3", "Three", "", "focus"),
    )


def test_active_focus_hours_exclude_unchanged_pause_and_cross_multiple_boundaries() -> None:
    service = FocusQuoteService(Preview(_quotes()), selector=lambda choices: choices[0])  # type: ignore[arg-type]
    first = service.select_for_session(show_quotes=True)
    assert first is not None and first.quote_id == "q1"
    assert service.quote_for_focus(3599) is first
    second = service.quote_for_focus(3600)
    assert second is not None and second.quote_id != first.quote_id
    assert service.quote_for_focus(3600) is second
    fourth = service.quote_for_focus(10_800)
    assert fourth is not None
    assert service.quote_for_focus(10_800) is fourth


def test_cycle_has_no_repeat_until_exhausted_and_weights_favorite() -> None:
    seen_candidate_counts: list[int] = []

    def select(choices: object) -> QuotePreview:
        values = list(choices)  # type: ignore[arg-type]
        seen_candidate_counts.append(len(values))
        return values[0]

    cycle = QuoteCycle(_quotes(), selector=select)
    selected = [cycle.next(), cycle.next(), cycle.next()]
    assert len({item.quote_id for item in selected if item is not None}) == 3
    assert seen_candidate_counts[0] == 4
    assert cycle.next() is not None
    assert cycle.next() != selected[-1]


def test_quote_crud_import_export_and_backups_are_atomic(tmp_path: Path) -> None:
    path = tmp_path / "quotes.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header_for("quotes"), lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "quote_id": "q1",
                "quote_text": "One",
                "author": "",
                "category": "focus",
                "is_active": "true",
                "is_favorite": "false",
            }
        )
    store = QuoteStore(path, tmp_path / "backups")
    custom = store.add("  New   thought  ", "Ada")
    assert custom.text == "New thought"
    store.set_favorite(custom.quote_id, True)
    store.set_active("q1", False)
    assert len(store.list_all()) == 2
    assert list((tmp_path / "backups" / "quotes").iterdir())
    exported = tmp_path / "copy.csv"
    store.export_copy(exported)
    assert exported.read_bytes() == path.read_bytes()
    assert store.import_validated(exported) == 2


def test_completion_sound_plays_once_and_respects_settings(tmp_path: Path) -> None:
    asset = tmp_path / "sound.wav"
    asset.write_bytes(b"RIFF-local-test")
    settings = SettingsService(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    settings.set_completion_sound_volume(35)
    backend = FakeBackend()
    sound = CompletionSoundService(settings, asset, backend_factory=lambda: backend)
    sound.begin_session()
    assert sound.play_planned_completion(session_enabled=True)
    assert not sound.play_planned_completion(session_enabled=True)
    assert backend.calls == [(asset, 0.35)]
    sound.begin_session()
    settings.set_completion_sound_enabled(False)
    assert not sound.play_planned_completion(session_enabled=True)
    settings.set_completion_sound_enabled(True)
    assert sound.preview()


def test_missing_sound_backend_or_asset_never_blocks_completion(tmp_path: Path) -> None:
    settings = SettingsService(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    missing = CompletionSoundService(settings, tmp_path / "missing.wav")
    assert not missing.play_planned_completion(session_enabled=True)
    asset = tmp_path / "sound.wav"
    asset.write_bytes(b"test")
    failing = CompletionSoundService(
        settings,
        asset,
        backend_factory=lambda: (_ for _ in ()).throw(RuntimeError("no backend")),
    )
    assert not failing.play_planned_completion(session_enabled=True)


@pytest.mark.parametrize(
    ("record", "message"),
    (
        (QuoteRecord("", "valid"), "ID is invalid"),
        (QuoteRecord("q", "valid", is_active=1), "flags must be Boolean"),  # type: ignore[arg-type]
        (QuoteRecord("q", 7), "must be text"),  # type: ignore[arg-type]
        (QuoteRecord("q", "x" * 501), "cannot exceed"),
        (QuoteRecord("q", "bad\x00text"), "control characters"),
    ),
)
def test_quote_record_validation_rejects_unsafe_values(record: QuoteRecord, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        QuoteStore._validated(record)


def test_quote_store_rejects_missing_duplicate_invalid_import_and_self_export(
    tmp_path: Path,
) -> None:
    store = _quote_store_for_validation(tmp_path)
    with pytest.raises(LookupError, match="not found"):
        store.update("missing", text="Still missing")
    with pytest.raises(ValueError, match="destination must differ"):
        store.export_copy(store.path)
    invalid = tmp_path / "invalid.csv"
    invalid.write_text("wrong,header\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid quote CSV"):
        store.import_validated(invalid)
    duplicate = QuoteRecord("same", "One")
    with pytest.raises(ValueError, match="must be unique"):
        store._save((duplicate, QuoteRecord("same", "Two")))


def _quote_store_for_validation(tmp_path: Path) -> QuoteStore:
    path = tmp_path / "quotes.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header_for("quotes"), lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "quote_id": "q1",
                "quote_text": "One",
                "author": "",
                "category": "focus",
                "is_active": "true",
                "is_favorite": "false",
            }
        )
    return QuoteStore(path, tmp_path / "backups")
