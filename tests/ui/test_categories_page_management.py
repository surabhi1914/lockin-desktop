from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from app.services.category_service import OTHER_CATEGORY_ID
from app.ui.dialogs.archive_category_dialog import ArchiveCategoryDialog
from app.ui.dialogs.rename_category_dialog import RenameCategoryDialog
from app.ui.pages.categories_page import CategoriesPage
from tests.phase3_helpers import isolated_category_service, path_config


def test_page_updates_immediately_for_create_rename_archive_restore(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    page = CategoriesPage(service)
    qtbot.addWidget(page)  # type: ignore[attr-defined]
    try:
        assert len(page.category_rows) == 9
        created = service.create("Portfolio Work")
        assert any(row.category.category_id == created.category_id for row in page.category_rows)
        service.rename(created.category_id, "Portfolio Projects")
        assert any(row.category.category_name == "Portfolio Projects" for row in page.category_rows)
        service.archive(created.category_id)
        row = next(
            row for row in page.category_rows if row.category.category_id == created.category_id
        )
        assert row.restore_button.isVisibleTo(page)
        service.restore(created.category_id)
        row = next(
            row for row in page.category_rows if row.category.category_id == created.category_id
        )
        assert row.category.is_active
    finally:
        connection.close()


def test_search_filter_and_other_protection(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    page = CategoriesPage(service)
    qtbot.addWidget(page)  # type: ignore[attr-defined]
    try:
        page.search_input.setText("Machine")
        assert [row.category.category_name for row in page.category_rows] == ["Machine Learning"]
        page.search_input.clear()
        other = next(
            row for row in page.category_rows if row.category.category_id == OTHER_CATEGORY_ID
        )
        assert not other.rename_button.isEnabled()
        assert not other.archive_button.isEnabled()
        service.archive(
            next(item.category_id for item in service.list_active() if item.category_name == "DSA")
        )
        page.filter_combo.setCurrentIndex(page.filter_combo.findData("archived"))
        assert all(not row.category.is_active for row in page.category_rows)
    finally:
        connection.close()


def test_rename_and_archive_dialogs_perform_real_mutations(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    category = service.create("Writing")
    try:
        rename = RenameCategoryDialog(service, category)
        qtbot.addWidget(rename)  # type: ignore[attr-defined]
        rename.name_input.setText("DSA")
        assert rename.validation.isVisibleTo(rename)
        assert not rename.save_button.isEnabled()
        rename.name_input.setText("Long-form Writing")
        qtbot.mouseClick(rename.save_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert rename.result() == QDialog.DialogCode.Accepted
        renamed = service.resolve_selected_category(category.category_id)
        assert renamed.category_name == "Long-form Writing"

        archive = ArchiveCategoryDialog(service, renamed)
        qtbot.addWidget(archive)  # type: ignore[attr-defined]
        archive_button = archive.buttons.button(QDialogButtonBox.StandardButton.Yes)
        qtbot.mouseClick(archive_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert archive.result() == QDialog.DialogCode.Accepted
        assert not service.repository.get_by_id(category.category_id).is_active
    finally:
        connection.close()


def test_archive_dialog_reports_protected_other_error(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    try:
        other = service.resolve_selected_category(OTHER_CATEGORY_ID)
        dialog = ArchiveCategoryDialog(service, other)
        qtbot.addWidget(dialog)  # type: ignore[attr-defined]
        archive_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Yes)
        qtbot.mouseClick(archive_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert dialog.result() == QDialog.DialogCode.Rejected
        assert dialog.validation.isVisibleTo(dialog)
    finally:
        connection.close()
