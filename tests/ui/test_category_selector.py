from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from app.ui.widgets.category_selector import CategorySelector
from tests.phase3_helpers import isolated_category_service, path_config


def test_selector_lists_active_only_and_search_text_is_not_silently_accepted(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    archived = next(item for item in service.list_active() if item.category_name == "Research")
    service.archive(archived.category_id)
    selector = CategorySelector(service)
    qtbot.addWidget(selector)  # type: ignore[attr-defined]
    try:
        assert selector.combo.count() == 8
        assert selector.combo.findData(archived.category_id) == -1
        selector.combo.setEditText("Mach")
        selector._typed_text_changed("Mach")
        assert not selector.is_valid
        assert "+ Create" in selector.new_button.text()
        selector.combo.setEditText("machine learning")
        selector._typed_text_changed("machine learning")
        assert selector.is_valid
    finally:
        connection.close()


def test_selector_preserves_selection_and_archival_invalidates_it(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    selected = next(item for item in service.list_active() if item.category_name == "Projects")
    selector = CategorySelector(service, selected_category_id=selected.category_id)
    qtbot.addWidget(selector)  # type: ignore[attr-defined]
    try:
        service.create("Unrelated")
        assert selector.selected_category_id == selected.category_id
        service.archive(selected.category_id)
        assert not selector.is_valid
        assert "archived or unavailable" in selector.validation.text()
    finally:
        connection.close()


def test_inline_creation_selects_new_category(
    qapp: QApplication, qtbot: object, tmp_path: Path, monkeypatch: object
) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    selector = CategorySelector(service)
    qtbot.addWidget(selector)  # type: ignore[attr-defined]

    class FakeDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, category_service: object, *, initial_name: str, parent: object) -> None:
            del category_service, parent
            self.created_category = service.create(initial_name)

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "app.ui.widgets.category_selector.CreateCategoryDialog", FakeDialog
    )
    try:
        selector.combo.setEditText("Portfolio Work")
        selector._typed_text_changed("Portfolio Work")
        qtbot.mouseClick(selector.new_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert selector.selected_category() is not None
        assert selector.selected_category().category_name == "Portfolio Work"  # type: ignore[union-attr]
    finally:
        connection.close()
