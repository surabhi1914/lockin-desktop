import csv

from app.bootstrap import STARTER_CATEGORIES, run_phase0_bootstrap
from app.core.ids import starter_category_uuid
from app.core.paths import PathConfig
from app.portability.csv_contracts import CSV_CONTRACTS, header_for
from app.portability.csv_validation import validate_csv
from app.portability.manifest import load_manifest


def test_complete_portable_contract(isolated_config: PathConfig) -> None:
    result = run_phase0_bootstrap(config=isolated_config)
    assert result.success, result.errors
    root = isolated_config.portable_root
    manifest = load_manifest(root / "manifest.json")
    assert manifest.primary_timezone == "America/Detroit"
    assert manifest.partitioning.max_file_size_bytes == 10_485_760
    for entity in ("devices", "categories", "quotes", "daily_goals"):
        path = root / f"{entity}.csv"
        assert validate_csv(path, entity) == ()
        with path.open("r", encoding="utf-8", newline="") as handle:
            assert tuple(next(csv.reader(handle))) == header_for(entity)
    for directory in ("sessions", "segments", "distractions"):
        assert (root / directory).is_dir()
    with (root / "categories.csv").open("r", encoding="utf-8", newline="") as handle:
        categories = list(csv.DictReader(handle))
    assert [row["category_name"] for row in categories] == list(STARTER_CATEGORIES)
    assert [row["category_id"] for row in categories] == [
        starter_category_uuid(name) for name in STARTER_CATEGORIES
    ]
    for header in CSV_CONTRACTS.values():
        assert not any("intention" in column for column in header)
