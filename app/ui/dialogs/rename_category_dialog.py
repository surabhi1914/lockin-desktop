"""Category rename dialog with prefilled input and recoverable validation."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.category import Category, normalize_category_name
from app.models.errors import CategoryError
from app.services.category_service import CategoryService
from app.ui.widgets.validation_message import ValidationMessage


class RenameCategoryDialog(QDialog):
    def __init__(
        self,
        category_service: CategoryService,
        category: Category,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rename Category")
        self.setModal(True)
        self._service = category_service
        self._category = category
        self.renamed_category: Category | None = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit(category.category_name)
        self.name_input.setObjectName("renameCategoryName")
        self.name_input.setAccessibleName("Renamed category name")
        self.name_input.setMaxLength(80)
        form.addRow("Name", self.name_input)
        layout.addLayout(form)
        self.validation = ValidationMessage()
        layout.addWidget(self.validation)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.buttons.accepted.connect(self._submit)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.name_input.textChanged.connect(self._validate)
        self._validate()

    def _validate(self) -> None:
        try:
            name = normalize_category_name(self.name_input.text())
            duplicate = self._service.repository.find_by_normalized_name(name)
            if duplicate is not None and duplicate.category_id != self._category.category_id:
                raise CategoryError(f"A category named {duplicate.category_name!r} already exists.")
        except CategoryError as exc:
            self.validation.set_error(str(exc))
            self.save_button.setEnabled(False)
        else:
            self.validation.clear_error()
            self.save_button.setEnabled(name != self._category.category_name)

    def _submit(self) -> None:
        try:
            self.renamed_category = self._service.rename(
                self._category.category_id, self.name_input.text()
            )
        except CategoryError as exc:
            self.validation.set_error(str(exc))
            return
        self.accept()
