"""Pure device-to-portable-row mapping."""

from app.core.checksums import record_checksum
from app.core.constants import DATA_SCHEMA_VERSION
from app.models.persisted_device import PersistedDevice
from app.models.portable_sync import PortableRow
from app.portability.csv_contracts import DEVICES_HEADER
from app.portability.csv_mapping import ordered_row


def map_device(device: PersistedDevice) -> PortableRow:
    values = ordered_row(
        DEVICES_HEADER,
        {
            "schema_version": DATA_SCHEMA_VERSION,
            "device_id": device.device_id,
            "device_label": device.device_label,
            "created_at_utc": device.created_at_utc,
            "updated_at_utc": device.updated_at_utc,
        },
    )
    return PortableRow(
        "devices",
        "device",
        device.device_id,
        record_checksum(values),
        None,
        values,
        (device.device_id,),
    )
