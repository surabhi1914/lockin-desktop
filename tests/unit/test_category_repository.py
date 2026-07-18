import sqlite3

import pytest

from app.database.repositories.category_repository import CategoryRepository
from app.models.category import Category
from app.models.errors import CategoryNotFoundError, DuplicateCategoryError
from tests.phase3_helpers import memory_category_connection


def _category(category_id: str, name: str, *, active: bool = True) -> Category:
    return Category(
        category_id,
        name,
        None,
        active,
        "2026-07-16T20:00:00Z",
        "2026-07-16T20:00:00Z",
    )


@pytest.fixture
def repository() -> tuple[CategoryRepository, sqlite3.Connection]:
    connection = memory_category_connection()
    return CategoryRepository(connection), connection


def test_create_list_find_and_count(
    repository: tuple[CategoryRepository, sqlite3.Connection],
) -> None:
    repo, connection = repository
    created = repo.create(_category("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "Portfolio Work"))
    connection.commit()
    assert repo.count() == 1
    assert repo.list_active() == (created,)
    assert repo.find_by_normalized_name(" portfolio   WORK ") == created
    assert repo.get_by_id(created.category_id) == created


def test_duplicate_normalized_name_is_rejected(
    repository: tuple[CategoryRepository, sqlite3.Connection],
) -> None:
    repo, _ = repository
    repo.create(_category("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "Machine Learning"))
    with pytest.raises(DuplicateCategoryError):
        repo.create(_category("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", " machine   LEARNING "))


def test_rename_archive_restore_preserve_stable_id(
    repository: tuple[CategoryRepository, sqlite3.Connection],
) -> None:
    repo, _ = repository
    original = repo.create(_category("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "Portfolio Work"))
    renamed = repo.rename(original.category_id, "Portfolio Projects", "2026-07-16T21:00:00Z")
    assert renamed.category_id == original.category_id
    archived = repo.archive(original.category_id, "2026-07-16T22:00:00Z")
    assert not archived.is_active and repo.count() == 1
    assert repo.list_active() == ()
    restored = repo.restore(original.category_id, "2026-07-16T23:00:00Z")
    assert restored.is_active and restored.category_id == original.category_id


def test_rename_collision_and_missing_id_are_typed(
    repository: tuple[CategoryRepository, sqlite3.Connection],
) -> None:
    repo, _ = repository
    first = repo.create(_category("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "One"))
    second = repo.create(_category("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "Two"))
    with pytest.raises(DuplicateCategoryError):
        repo.rename(second.category_id, first.category_name, "2026-07-16T21:00:00Z")
    with pytest.raises(CategoryNotFoundError):
        repo.get_by_id("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def test_sql_injection_text_is_data_not_sql(
    repository: tuple[CategoryRepository, sqlite3.Connection],
) -> None:
    repo, connection = repository
    value = "Focus'); DROP TABLE categories; --"
    repo.create(_category("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", value))
    connection.commit()
    assert repo.get_by_id("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa").category_name == value
    assert repo.count() == 1
