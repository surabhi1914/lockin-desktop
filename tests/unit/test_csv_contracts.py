from types import MappingProxyType

import pytest

from app.portability.csv_contracts import CSV_CONTRACTS, header_for


def test_contracts_are_ordered_and_immutable() -> None:
    assert isinstance(CSV_CONTRACTS, MappingProxyType)
    assert header_for("devices")[:2] == ("schema_version", "device_id")
    assert header_for("sessions")[-1] == "record_checksum"


def test_unknown_contract_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        header_for("intentions")


def test_temporary_intention_absent_from_every_contract() -> None:
    for header in CSV_CONTRACTS.values():
        assert all("intention" not in column for column in header)
