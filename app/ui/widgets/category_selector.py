"""Searchable active-category selector with inline creation."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QCompleter, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from app.models.category import Category, category_uniqueness_key
from app.models.errors import CategoryError
from app.services.category_service import CategoryService
from app.ui.dialogs.create_category_dialog import CreateCategoryDialog
from app.ui.widgets.validation_message import ValidationMessage


class CategorySelector(QWidget):
    """Select only an active persisted category; typed text is never silently accepted."""

    selection_changed = Signal(object)
    validity_changed = Signal(bool)

    def __init__(
        self,
        category_service: CategoryService,
        *,
        selected_category_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("categorySelector")
        self._service = category_service
        self._selected_category_id = selected_category_id
        self._categories: tuple[Category, ...] = ()
        self._refreshing = False
        self._last_valid = False
        self._selection_unavailable = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        row = QHBoxLayout()
        self.combo = QComboBox()
        self.combo.setObjectName("categoryCombo")
        self.combo.setAccessibleName("Search or select an active category")
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo.setPlaceholderText("Search/select category")
        completer = QCompleter(self.combo.model(), self.combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.combo.setCompleter(completer)
        self.new_button = QPushButton("+ New Category")
        self.new_button.setObjectName("newCategoryButton")
        self.new_button.clicked.connect(self._open_create_dialog)
        row.addWidget(self.combo, 1)
        row.addWidget(self.new_button)
        layout.addLayout(row)
        self.validation = ValidationMessage()
        self.validation.setAccessibleName("Category selection error")
        layout.addWidget(self.validation)
        self.combo.currentIndexChanged.connect(self._index_changed)
        line_edit = self.combo.lineEdit()
        if line_edit is not None:
            line_edit.textEdited.connect(self._typed_text_changed)
        self._unsubscribe = self._service.subscribe(self.refresh)
        self.destroyed.connect(self._on_destroyed)
        self.refresh()

    @property
    def selected_category_id(self) -> str | None:
        category = self.selected_category()
        return category.category_id if category is not None else None

    @property
    def is_valid(self) -> bool:
        return self.selected_category() is not None

    def selected_category(self) -> Category | None:
        text = self.combo.currentText()
        try:
            key = category_uniqueness_key(text)
        except CategoryError:
            return None
        return next((item for item in self._categories if item.normalized_name == key), None)

    def set_selected_category(self, category_id: str | None) -> None:
        self._selected_category_id = category_id
        self._selection_unavailable = category_id is not None and not self._select_id(category_id)
        self._validate_selection()

    def refresh(self) -> None:
        preserve = self.selected_category_id or self._selected_category_id
        self._categories = self._service.list_active()
        self._refreshing = True
        self.combo.clear()
        for category in self._categories:
            label = (
                f"{category.category_icon} {category.category_name}"
                if category.category_icon
                else category.category_name
            )
            self.combo.addItem(label, category.category_id)
            self.combo.setItemData(
                self.combo.count() - 1,
                category.category_name,
                Qt.ItemDataRole.AccessibleTextRole,
            )
        self._refreshing = False
        if preserve is not None and self._select_id(preserve):
            self._selected_category_id = preserve
            self._selection_unavailable = False
        elif preserve is not None:
            self.combo.setCurrentIndex(-1)
            self.combo.setEditText("")
            self._selected_category_id = preserve
            self._selection_unavailable = True
        elif self._categories:
            self.combo.setCurrentIndex(0)
            self._selected_category_id = self._categories[0].category_id
            self._selection_unavailable = False
        else:
            self.combo.setCurrentIndex(-1)
            self._selection_unavailable = False
        completer = self.combo.completer()
        if completer is not None:
            completer.setModel(self.combo.model())
        self._validate_selection()

    def _select_id(self, category_id: str | None) -> bool:
        if category_id is None:
            self.combo.setCurrentIndex(-1)
            return False
        index = self.combo.findData(category_id)
        if index < 0:
            return False
        self.combo.setCurrentIndex(index)
        category = next(item for item in self._categories if item.category_id == category_id)
        self.combo.setEditText(category.category_name)
        return True

    def _index_changed(self, index: int) -> None:
        if self._refreshing:
            return
        category_id = self.combo.itemData(index) if index >= 0 else None
        if isinstance(category_id, str):
            self._selected_category_id = category_id
            self._selection_unavailable = False
            category = next(item for item in self._categories if item.category_id == category_id)
            self.combo.setEditText(category.category_name)
        self._validate_selection()
        self.selection_changed.emit(self.selected_category_id)

    def _typed_text_changed(self, text: str) -> None:
        self._selection_unavailable = False
        category = self._match_name(text)
        if category is not None:
            self._selected_category_id = category.category_id
        self._validate_selection()
        self.selection_changed.emit(self.selected_category_id)

    def _match_name(self, text: str) -> Category | None:
        try:
            key = category_uniqueness_key(text)
        except CategoryError:
            return None
        return next((item for item in self._categories if item.normalized_name == key), None)

    def _validate_selection(self) -> None:
        category = self.selected_category()
        valid = category is not None
        typed = self.combo.currentText().strip()
        if not self._categories:
            self.validation.set_error("No active categories. Create or restore one to continue.")
            self.new_button.setText("+ New Category")
        elif self._selection_unavailable and not valid:
            self.validation.set_error(
                "The previously selected category is archived or unavailable. Choose another."
            )
            self.new_button.setText("+ New Category")
        elif not valid:
            self.validation.set_error(
                "Choose an active category from the list or create the typed category."
            )
            self.new_button.setText(f"+ Create {typed!r}" if typed else "+ New Category")
        elif category is not None:
            self.validation.clear_error()
            self.new_button.setText("+ New Category")
            self._selected_category_id = category.category_id
        if valid != self._last_valid:
            self._last_valid = valid
            self.validity_changed.emit(valid)

    def _open_create_dialog(self) -> None:
        initial = self.combo.currentText() if self.selected_category() is None else ""
        dialog = CreateCategoryDialog(self._service, initial_name=initial, parent=self)
        if dialog.exec() == CreateCategoryDialog.DialogCode.Accepted:
            created = dialog.created_category
            if created is not None:
                self.set_selected_category(created.category_id)
                self.selection_changed.emit(created.category_id)

    def _on_destroyed(self, _value: object = None) -> None:
        self._unsubscribe()
