"""Inline category creation dialog."""

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


class CreateCategoryDialog(QDialog):
    def __init__(
        self,
        category_service: CategoryService,
        *,
        initial_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Category")
        self.setModal(True)
        self._service = category_service
        self.created_category: Category | None = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit(initial_name)
        self.name_input.setObjectName("createCategoryName")
        self.name_input.setAccessibleName("New category name")
        self.name_input.setMaxLength(80)
        self.icon_input = QLineEdit()
        self.icon_input.setObjectName("createCategoryIcon")
        self.icon_input.setAccessibleName("Optional category icon")
        self.icon_input.setMaxLength(16)
        form.addRow("Name", self.name_input)
        form.addRow("Icon — optional", self.icon_input)
        layout.addLayout(form)
        self.validation = ValidationMessage()
        layout.addWidget(self.validation)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setObjectName("createCategorySave")
        self.buttons.accepted.connect(self._submit)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.name_input.textChanged.connect(self._validate)
        self.icon_input.textChanged.connect(self._validate)
        self._validate()

    def _validate(self) -> None:
        try:
            name = normalize_category_name(self.name_input.text())
            icon = self.icon_input.text().strip()
            if len(icon) > 16:
                raise CategoryError("category icon cannot exceed 16 characters")
            duplicate = self._service.repository.find_by_normalized_name(name)
            if duplicate is not None:
                raise CategoryError(f"A category named {duplicate.category_name!r} already exists.")
        except CategoryError as exc:
            self.validation.set_error(str(exc))
            self.save_button.setEnabled(False)
        else:
            self.validation.clear_error()
            self.save_button.setEnabled(True)

    def _submit(self) -> None:
        try:
            self.created_category = self._service.create(
                self.name_input.text(), self.icon_input.text() or None
            )
        except CategoryError as exc:
            self.validation.set_error(str(exc))
            self.save_button.setEnabled(False)
            return
        self.accept()
