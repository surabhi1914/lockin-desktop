"""Pure distraction-to-portable-row mapping."""

from dataclasses import fields

from app.models.persisted_distraction import PersistedDistraction
from app.models.portable_sync import PortableRow
from app.portability.csv_contracts import DISTRACTIONS_HEADER
from app.portability.csv_mapping import csv_bool, ordered_row, portable_row_checksum


def map_distraction(distraction: PersistedDistraction, exported_at_utc: str) -> PortableRow:
    values = ordered_row(
        DISTRACTIONS_HEADER,
        {
            **{
                field: getattr(distraction, field)
                for field in (item.name for item in fields(distraction))
            },
            "is_overtime": csv_bool(distraction.is_overtime),
            "exported_at_utc": exported_at_utc,
        },
    )
    checksum = portable_row_checksum(values)
    values["record_checksum"] = checksum
    return PortableRow(
        "distractions",
        "distraction",
        distraction.distraction_id,
        checksum,
        distraction.local_date,
        values,
        (distraction.marked_at_utc, distraction.session_id, distraction.distraction_id),
    )
