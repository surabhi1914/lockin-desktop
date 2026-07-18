from uuid import UUID

import pytest

from app.core.errors import ValidationError
from app.core.ids import canonicalize_uuid, new_uuid4, starter_category_uuid


def test_uuid4_format_and_version() -> None:
    value = new_uuid4()
    assert value == value.lower()
    assert UUID(value).version == 4


def test_uuid_canonicalization() -> None:
    value = "550E8400-E29B-41D4-A716-446655440000"
    assert canonicalize_uuid(value) == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.parametrize("value", ["", "not-a-uuid"])
def test_invalid_uuid_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        canonicalize_uuid(value)


def test_starter_uuid_is_deterministic_and_normalized() -> None:
    assert starter_category_uuid(" Machine   Learning ") == starter_category_uuid(
        "machine learning"
    )
    assert UUID(starter_category_uuid("DSA")).version == 5


def test_empty_starter_name_rejected() -> None:
    with pytest.raises(ValidationError):
        starter_category_uuid("   ")
