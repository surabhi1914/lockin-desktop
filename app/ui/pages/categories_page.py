"""Functional permanent category-management page for Phase 3."""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.category import Category
from app.models.errors import CategoryError
from app.services.category_service import OTHER_CATEGORY_ID, CategoryService
from app.ui.dialogs import ArchiveCategoryDialog, CreateCategoryDialog, RenameCategoryDialog
from app.ui.widgets import EmptyState, PageHeader, ValidationMessage


class CategoryRow(QFrame):
    def __init__(
        self,
        category: Category,
        *,
        rename_callback: Callable[[bool], None],
        archive_callback: Callable[[bool], None],
        restore_callback: Callable[[bool], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.category = category
        self.setProperty("card", True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        text = QVBoxLayout()
        name = QLabel(
            f"{category.category_icon}  {category.category_name}"
            if category.category_icon
            else category.category_name
        )
        name.setStyleSheet("font-weight: 600;")
        badge = QLabel("Active" if category.is_active else "Archived")
        badge.setProperty("muted", True)
        text.addWidget(name)
        text.addWidget(badge)
        layout.addLayout(text, 1)
        self.rename_button = QPushButton("Rename", self)
        self.archive_button = QPushButton("Archive", self)
        self.restore_button = QPushButton("Restore", self)
        self.rename_button.clicked.connect(rename_callback)
        self.archive_button.clicked.connect(archive_callback)
        self.restore_button.clicked.connect(restore_callback)
        layout.addWidget(self.rename_button)
        layout.addWidget(self.archive_button)
        layout.addWidget(self.restore_button)
        protected = category.category_id == OTHER_CATEGORY_ID
        self.rename_button.setVisible(category.is_active)
        self.archive_button.setVisible(category.is_active)
        self.restore_button.setVisible(not category.is_active)
        self.rename_button.setEnabled(not protected)
        self.archive_button.setEnabled(not protected)
        if protected:
            explanation = "Other is the protected fallback category."
            self.rename_button.setToolTip(explanation)
            self.archive_button.setToolTip(explanation)
        state = "active" if category.is_active else "archived"
        self.setAccessibleName(f"Category {category.category_name}, {state}")


class CategoriesPage(QWidget):
    def __init__(self, category_service: CategoryService) -> None:
        super().__init__()
        self.setObjectName("page_categories")
        self._service = category_service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(
            PageHeader(
                "Categories",
                "Create, rename, archive, or restore permanent categories. Other is protected.",
            )
        )
        controls = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setObjectName("categorySearch")
        self.search_input.setPlaceholderText("Search categories")
        self.search_input.setAccessibleName("Search categories")
        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("categoryStatusFilter")
        self.filter_combo.addItem("All", "all")
        self.filter_combo.addItem("Active", "active")
        self.filter_combo.addItem("Archived", "archived")
        self.create_button = QPushButton("+ New Category")
        self.create_button.setObjectName("categoriesCreateButton")
        self.create_button.clicked.connect(self._create)
        controls.addWidget(self.search_input, 1)
        controls.addWidget(self.filter_combo)
        controls.addWidget(self.create_button)
        layout.addLayout(controls)
        self.error = ValidationMessage()
        layout.addWidget(self.error)
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(8)
        layout.addWidget(self.rows_container)
        layout.addStretch(1)
        self.category_rows: list[CategoryRow] = []
        self.search_input.textChanged.connect(self.refresh)
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        self._unsubscribe = self._service.subscribe(self.refresh)
        self.destroyed.connect(self._on_destroyed)
        self.refresh()

    def refresh(self) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.category_rows.clear()
        query = self.search_input.text().strip().casefold()
        selected_filter = self.filter_combo.currentData()
        categories = self._service.repository.list_all()
        visible = tuple(
            category
            for category in categories
            if query in category.category_name.casefold()
            and (
                selected_filter == "all"
                or (selected_filter == "active" and category.is_active)
                or (selected_filter == "archived" and not category.is_active)
            )
        )
        if not visible:
            empty = EmptyState(
                "No matching categories",
                "Adjust the search/filter or create a new permanent category.",
            )
            self.rows_layout.addWidget(empty)
            return
        for category in visible:

            def rename(_checked: bool = False, item: Category = category) -> None:
                self._rename(item)

            def archive(_checked: bool = False, item: Category = category) -> None:
                self._archive(item)

            def restore(_checked: bool = False, item: Category = category) -> None:
                self._restore(item)

            row = CategoryRow(
                category,
                rename_callback=rename,
                archive_callback=archive,
                restore_callback=restore,
                parent=self.rows_container,
            )
            self.category_rows.append(row)
            self.rows_layout.addWidget(row)

    def _create(self) -> None:
        dialog = CreateCategoryDialog(self._service, parent=self)
        dialog.exec()

    def _rename(self, category: Category) -> None:
        dialog = RenameCategoryDialog(self._service, category, self)
        dialog.exec()

    def _archive(self, category: Category) -> None:
        dialog = ArchiveCategoryDialog(self._service, category, self)
        dialog.exec()

    def _restore(self, category: Category) -> None:
        try:
            self._service.restore(category.category_id)
        except CategoryError as exc:
            self.error.set_error(str(exc))
        else:
            self.error.clear_error()

    def _on_destroyed(self, _value: object = None) -> None:
        self._unsubscribe()
