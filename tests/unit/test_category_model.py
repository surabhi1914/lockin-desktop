from dataclasses import FrozenInstanceError

import pytest

from app.models.category import Category, category_uniqueness_key, normalize_category_name
from app.models.errors import CategoryError


def _category(**changes: object) -> Category:
    values: dict[str, object] = {
        "category_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "category_name": "Machine Learning",
        "category_icon": "\U0001f9e0",
        "is_active": True,
        "created_at_utc": "2026-07-16T20:00:00Z",
        "updated_at_utc": "2026-07-16T20:00:00Z",
    }
    values.update(changes)
    return Category(**values)  # type: ignore[arg-type]


def test_category_is_valid_immutable_and_normalizes_whitespace() -> None:
    category = _category(category_name="  Machine   Learning  ")
    assert category.category_name == "Machine Learning"
    assert category.normalized_name == "machine learning"
    with pytest.raises(FrozenInstanceError):
        category.category_name = "Changed"  # type: ignore[misc]


def test_unicode_and_emoji_are_allowed() -> None:
    category = _category(
        category_name="\u6df1\u3044 \u4f5c\u696d \U0001f680",
        category_icon="\U0001f331",
    )
    assert category.category_name == "\u6df1\u3044 \u4f5c\u696d \U0001f680"
    assert category.category_icon == "\U0001f331"


@pytest.mark.parametrize("name", ["", "   ", "bad\nname", "bad\tname", "x" * 61])
def test_invalid_category_names_are_rejected(name: str) -> None:
    with pytest.raises(CategoryError):
        _category(category_name=name)


def test_invalid_uuid_timestamp_icon_and_bool_are_rejected() -> None:
    with pytest.raises(CategoryError):
        _category(category_id="not-a-uuid")
    with pytest.raises(CategoryError):
        _category(category_id="AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA")
    with pytest.raises(CategoryError):
        _category(created_at_utc="2026-07-16")
    with pytest.raises(CategoryError):
        _category(category_icon="x" * 17)
    with pytest.raises(CategoryError):
        _category(is_active=1)


def test_uniqueness_normalization_collapses_and_casefolds() -> None:
    assert category_uniqueness_key(" machine   LEARNING ") == "machine learning"
    assert normalize_category_name("  Portfolio   Work ") == "Portfolio Work"
