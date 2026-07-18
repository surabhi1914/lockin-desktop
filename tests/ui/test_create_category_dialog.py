from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from app.ui.dialogs.create_category_dialog import CreateCategoryDialog
from tests.phase3_helpers import isolated_category_service, path_config


def test_create_dialog_validation_duplicate_and_success(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    service, connection, store = isolated_category_service(path_config(tmp_path))
    dialog = CreateCategoryDialog(service)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    try:
        assert not dialog.save_button.isEnabled()
        dialog.name_input.setText(" machine   learning ")
        assert not dialog.save_button.isEnabled()
        assert "already exists" in dialog.validation.text()
        dialog.name_input.setText("Portfolio Work")
        dialog.icon_input.setText("P")
        assert dialog.save_button.isEnabled()
        qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert dialog.created_category is not None
        assert dialog.created_category.category_name == "Portfolio Work"
        assert dialog.created_category.category_id in {
            category.category_id for category in store.load()
        }
    finally:
        connection.close()


def test_cancel_changes_nothing(qapp: QApplication, qtbot: object, tmp_path: Path) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    dialog = CreateCategoryDialog(service, initial_name="Not Created")
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    before = service.repository.count()
    try:
        qtbot.keyClick(dialog, Qt.Key.Key_Escape)  # type: ignore[attr-defined]
        assert dialog.result() == QDialog.DialogCode.Rejected
        assert service.repository.count() == before
    finally:
        connection.close()
