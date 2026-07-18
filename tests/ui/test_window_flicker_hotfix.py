"""Regression coverage for the v1.0.1 transient-window hotfix."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, QProcess
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from app.models.errors import CategoryError
from app.ui.pages import categories_page as categories_page_module
from app.ui.pages.categories_page import CategoriesPage
from tests.phase3_helpers import isolated_category_service, path_config


class _ParentlessButtonShowSpy(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.shown: list[QPushButton] = []

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.Show
            and isinstance(watched, QPushButton)
            and watched.parentWidget() is None
        ):
            self.shown.append(watched)
        return False


def test_category_refresh_never_shows_parentless_action_buttons(
    qapp: QApplication, qtbot: Any, tmp_path: Path
) -> None:
    service, connection, _store = isolated_category_service(path_config(tmp_path))
    spy = _ParentlessButtonShowSpy()
    qapp.installEventFilter(spy)
    try:
        page = CategoriesPage(service)
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page.search_input.setText("machine")
        page.search_input.clear()
        page.filter_combo.setCurrentIndex(page.filter_combo.findData("active"))
        qapp.processEvents()

        assert spy.shown == []
        assert page.category_rows
        for row in page.category_rows:
            assert row.parentWidget() is page.rows_container
            for button in (row.rename_button, row.archive_button, row.restore_button):
                assert button.parentWidget() is row
                assert not button.isWindow()
    finally:
        qapp.removeEventFilter(spy)
        connection.close()


def test_ordinary_ui_interactions_do_not_launch_processes(
    app_context: Any, qapp: QApplication, monkeypatch: Any
) -> None:
    attempts: list[str] = []

    def fail(api: str) -> Any:
        def record(*_args: Any, **_kwargs: Any) -> Any:
            attempts.append(api)
            raise AssertionError(f"unexpected process launch through {api}")

        return record

    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, fail(f"subprocess.{name}"))
    monkeypatch.setattr(os, "system", fail("os.system"))
    if hasattr(os, "startfile"):
        monkeypatch.setattr(os, "startfile", fail("os.startfile"))
    monkeypatch.setattr(QProcess, "start", fail("QProcess.start"))
    monkeypatch.setattr(QProcess, "startDetached", fail("QProcess.startDetached"))

    window = app_context.window
    for page_id in app_context.page_registry.page_ids:
        window.sidebar.button_for(page_id).click()
    categories = window.page("categories")
    assert isinstance(categories, CategoriesPage)
    categories.search_input.setText("focus")
    categories.search_input.clear()
    categories.filter_combo.setCurrentIndex(categories.filter_combo.findData("active"))
    window.sidebar.collapse_button.click()
    window.sidebar.collapse_button.click()
    qapp.processEvents()

    assert attempts == []


def test_navigation_reuses_pages_and_preserves_the_main_native_window(
    app_context: Any, qapp: QApplication, qtbot: Any
) -> None:
    window = app_context.window
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    original_pages = dict(window.pages)
    original_window_id = int(window.winId())
    original_top_levels = {
        id(widget) for widget in QApplication.topLevelWidgets() if widget.isVisible()
    }

    for _cycle in range(3):
        for page_id in app_context.page_registry.page_ids:
            window.sidebar.button_for(page_id).click()
            qapp.processEvents()
            assert window.page(page_id) is original_pages[page_id]
            assert window.isVisible()
            assert int(window.winId()) == original_window_id

    final_top_levels = {
        id(widget) for widget in QApplication.topLevelWidgets() if widget.isVisible()
    }
    assert final_top_levels == original_top_levels
    assert all(
        not (isinstance(widget, QWidget) and widget.isVisible() and widget.parentWidget() is None)
        or widget is window
        for widget in QApplication.topLevelWidgets()
    )


def test_category_refresh_action_callbacks_and_errors_remain_functional(
    qapp: QApplication, qtbot: Any, tmp_path: Path, monkeypatch: Any
) -> None:
    service, connection, _store = isolated_category_service(path_config(tmp_path))
    opened: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    class FakeDialog:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            opened.append((type(self).__name__, args, kwargs))

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(categories_page_module, "CreateCategoryDialog", FakeDialog)
    monkeypatch.setattr(categories_page_module, "RenameCategoryDialog", FakeDialog)
    monkeypatch.setattr(categories_page_module, "ArchiveCategoryDialog", FakeDialog)
    page = CategoriesPage(service)
    qtbot.addWidget(page)
    try:
        page.create_button.click()
        active = next(row for row in page.category_rows if row.archive_button.isEnabled())
        active.rename_button.click()
        active.archive_button.click()
        assert len(opened) == 3

        category = active.category
        service.archive(category.category_id)
        archived = next(
            row for row in page.category_rows if row.category.category_id == category.category_id
        )
        archived.restore_button.click()
        assert service.repository.get_by_id(category.category_id).is_active

        def fail_restore(_category_id: str) -> Any:
            raise CategoryError("deliberate restore failure")

        monkeypatch.setattr(service, "restore", fail_restore)
        page._restore(category)
        assert "deliberate restore failure" in page.error.text()
        page._on_destroyed()
    finally:
        connection.close()
