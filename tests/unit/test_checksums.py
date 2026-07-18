import pytest

from app.core.checksums import canonical_record_json, record_checksum
from app.core.errors import ValidationError


def test_checksum_stable_across_dictionary_order() -> None:
    first = {"text": "café", "count": 2, "active": True, "note": None}
    second = {"note": None, "active": True, "count": 2, "text": "café"}
    assert record_checksum(first) == record_checksum(second)
    assert canonical_record_json(first) == canonical_record_json(second)


def test_checksum_changes_with_value() -> None:
    assert record_checksum({"value": 1}) != record_checksum({"value": 2})
    assert len(record_checksum({"value": 1})) == 64


@pytest.mark.parametrize("value", [[1], {"nested": "value"}, 1.5])
def test_unsupported_checksum_value_rejected(value: object) -> None:
    with pytest.raises(ValidationError, match="Unsupported"):
        record_checksum({"value": value})


def test_non_string_checksum_key_rejected() -> None:
    with pytest.raises(ValidationError, match="keys"):
        canonical_record_json({1: "value"})  # type: ignore[dict-item]
