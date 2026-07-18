"""Searchable local quote management over atomic portable CSV storage."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.quotes.quote_store import QuoteRecord, QuoteStore
from app.services.portable_preview_service import PortablePreviewService
from app.ui.widgets import EmptyState, PageHeader


class QuotesPage(QWidget):
    def __init__(self, store: QuoteStore | PortablePreviewService) -> None:
        super().__init__()
        self.setObjectName("page_quotes")
        self._store = store
        self._read_only_preview = not hasattr(store, "list_all")
        self._visible: list[QuoteRecord] = []
        self.quote_rows: list[QuoteRecord] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(PageHeader("Quotes", "Search, curate, import, and export local quotes."))
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search quote or author")
        self.active_filter = QComboBox()
        self.active_filter.addItem("All", "all")
        self.active_filter.addItem("Active", "active")
        self.active_filter.addItem("Inactive", "inactive")
        filters.addWidget(self.search, 1)
        filters.addWidget(self.active_filter)
        layout.addLayout(filters)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(("Quote", "Author", "Active", "Favorite"))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        self.empty_state = EmptyState(
            "No matching quotes", "Add a custom quote or change the current filters."
        )
        layout.addWidget(self.empty_state)
        buttons = QHBoxLayout()
        self.add_button = QPushButton("Add custom quote")
        self.edit_button = QPushButton("Edit selected")
        self.active_button = QPushButton("Enable / Disable")
        self.favorite_button = QPushButton("Toggle favorite")
        self.import_button = QPushButton("Import CSV")
        self.export_button = QPushButton("Export copy")
        for button in (
            self.add_button,
            self.edit_button,
            self.active_button,
            self.favorite_button,
            self.import_button,
            self.export_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.search.textChanged.connect(self.refresh)
        self.active_filter.currentIndexChanged.connect(self.refresh)
        self.add_button.clicked.connect(self._add)
        self.edit_button.clicked.connect(self._edit)
        self.active_button.clicked.connect(self._toggle_active)
        self.favorite_button.clicked.connect(self._toggle_favorite)
        self.import_button.clicked.connect(self._import)
        self.export_button.clicked.connect(self._export)
        if self._read_only_preview:
            for button in (
                self.add_button,
                self.edit_button,
                self.active_button,
                self.favorite_button,
                self.import_button,
                self.export_button,
            ):
                button.setEnabled(False)
        self.refresh()

    def refresh(self) -> None:
        try:
            if isinstance(self._store, QuoteStore):
                records = self._store.list_all()
            else:
                count = self._store.active_quote_count()
                records = tuple(
                    QuoteRecord(
                        item.quote_id,
                        item.text,
                        item.author,
                        item.category,
                        item.is_active,
                        item.is_favorite,
                    )
                    for item in self._store.active_quotes(limit=count)
                )
        except (OSError, RuntimeError, ValueError) as exc:
            self.status.setText(str(exc))
            return
        query = self.search.text().strip().casefold()
        mode = str(self.active_filter.currentData())
        self._visible = [
            record
            for record in records
            if (not query or query in f"{record.text} {record.author}".casefold())
            and (mode == "all" or record.is_active == (mode == "active"))
        ]
        self.table.setRowCount(len(self._visible))
        self.table.setVisible(bool(self._visible))
        self.empty_state.setVisible(not self._visible)
        for row, record in enumerate(self._visible):
            values = (
                record.text,
                record.author,
                "Yes" if record.is_active else "No",
                "Yes" if record.is_favorite else "No",
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.status.setText(f"{len(self._visible)} of {len(records)} quotes shown")
        self.quote_rows = list(self._visible)

    def _selected(self) -> QuoteRecord | None:
        row = self.table.currentRow()
        return self._visible[row] if 0 <= row < len(self._visible) else None

    def _add(self) -> None:
        if not isinstance(self._store, QuoteStore):
            return
        store = self._store
        text, accepted = QInputDialog.getMultiLineText(self, "Add quote", "Quote")
        if not accepted:
            return
        author, accepted = QInputDialog.getText(self, "Add quote", "Author (optional)")
        if not accepted:
            return
        self._mutate(lambda: store.add(text, author))

    def _edit(self) -> None:
        if not isinstance(self._store, QuoteStore):
            return
        store = self._store
        selected = self._selected()
        if selected is None:
            return
        text, accepted = QInputDialog.getMultiLineText(self, "Edit quote", "Quote", selected.text)
        if accepted:
            self._mutate(lambda: store.update(selected.quote_id, text=text))

    def _toggle_active(self) -> None:
        if not isinstance(self._store, QuoteStore):
            return
        store = self._store
        selected = self._selected()
        if selected is not None:
            self._mutate(lambda: store.set_active(selected.quote_id, not selected.is_active))

    def _toggle_favorite(self) -> None:
        if not isinstance(self._store, QuoteStore):
            return
        store = self._store
        selected = self._selected()
        if selected is not None:
            self._mutate(lambda: store.set_favorite(selected.quote_id, not selected.is_favorite))

    def _import(self) -> None:
        if not isinstance(self._store, QuoteStore):
            return
        store = self._store
        source, _filter = QFileDialog.getOpenFileName(
            self, "Import validated quotes", "", "CSV (*.csv)"
        )
        if source:
            self._mutate(lambda: store.import_validated(Path(source)))

    def _export(self) -> None:
        if not isinstance(self._store, QuoteStore):
            return
        store = self._store
        destination, _filter = QFileDialog.getSaveFileName(
            self, "Export quote copy", "quotes.csv", "CSV (*.csv)"
        )
        if destination:
            self._mutate(lambda: store.export_copy(Path(destination)))

    def _mutate(self, action: Callable[[], object]) -> None:
        try:
            action()
            self.refresh()
        except (OSError, RuntimeError, ValueError, LookupError) as exc:
            QMessageBox.warning(self, "Quote update failed", str(exc))
