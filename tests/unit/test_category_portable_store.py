from pathlib import Path

import pytest

from app.models.category import Category
from app.models.errors import CategoryPersistenceError
from app.portability.category_portable_store import CategoryPortableStore
from app.portability.csv_contracts import header_for


def _category(category_id: str, name: str, active: bool) -> Category:
    return Category(
        category_id,
        name,
        "\U0001f331" if "Unicode" in name else None,
        active,
        "2026-07-16T20:00:00Z",
        "2026-07-16T20:00:00Z",
    )


def _store(tmp_path: Path) -> CategoryPortableStore:
    path = tmp_path / "portable" / "categories.csv"
    path.parent.mkdir(parents=True)
    path.write_text(",".join(header_for("categories")) + "\n", encoding="utf-8")
    return CategoryPortableStore(
        path,
        backup_directory=tmp_path / "runtime" / "backups",
        timestamp_provider=lambda: "2026-07-16T20:00:00Z",
    )


def test_write_load_exact_header_utf8_order_and_archived_preservation(tmp_path: Path) -> None:
    store = _store(tmp_path)
    active_z = _category("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "Unicode \U0001f680", True)
    active_a = _category("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "Alpha", True)
    archived = _category("cccccccc-cccc-4ccc-8ccc-cccccccccccc", "Beta", False)
    store.write((archived, active_z, active_a))
    lines = store.path.read_text(encoding="utf-8").splitlines()
    assert tuple(lines[0].split(",")) == header_for("categories")
    assert [item.category_name for item in store.load()] == [
        "Alpha",
        "Unicode \U0001f680",
        "Beta",
    ]
    assert store.load()[-1].is_active is False
    assert "temporary_intention" not in lines[0]


def test_populated_rewrite_creates_local_backup_and_cleans_temp(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = _category("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "First", True)
    second = _category("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "Second", True)
    store.write((first,))
    before = store.path.read_bytes()
    backup = store.write((first, second))
    assert backup is not None and backup.read_bytes() == before
    assert not list(store.path.parent.glob(".categories-*.tmp"))


def test_invalid_existing_file_is_never_overwritten(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.path.write_text("bad,header\npersonal,data\n", encoding="utf-8")
    original = store.path.read_bytes()
    with pytest.raises(CategoryPersistenceError):
        store.load()
    with pytest.raises(CategoryPersistenceError):
        store.write((_category("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "First", True),))
    assert store.path.read_bytes() == original
