"""Explicit category archive confirmation dialog."""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from app.models.category import Category
from app.models.errors import CategoryError
from app.services.category_service import CategoryService
from app.ui.widgets.validation_message import ValidationMessage


class ArchiveCategoryDialog(QDialog):
    def __init__(
        self,
        category_service: CategoryService,
        category: Category,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Archive Category")
        self.setModal(True)
        self._service = category_service
        self._category = category
        self.archived_category: Category | None = None
        layout = QVBoxLayout(self)
        message = QLabel(
            f"Archive {category.category_name!r}? It will disappear from focus setup but can "
            "be restored later."
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        self.validation = ValidationMessage()
        layout.addWidget(self.validation)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._submit)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _submit(self) -> None:
        try:
            self.archived_category = self._service.archive(self._category.category_id)
        except CategoryError as exc:
            self.validation.set_error(str(exc))
            return
        self.accept()
