"""Collapsible, persistent navigation sidebar."""

from types import MappingProxyType

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.page_registry import PageRegistry
from app.ui.widgets import IconButton


class Sidebar(QWidget):
    page_requested = Signal(str)
    collapsed_changed = Signal(bool)

    EXPANDED_WIDTH = 230
    COLLAPSED_WIDTH = 72

    def __init__(self, registry: PageRegistry, *, collapsed: bool = False) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        self._registry = registry
        self._collapsed = False
        self._buttons: dict[str, QPushButton] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 14)
        layout.setSpacing(7)
        self.brand_label = QLabel("LOCKIN")
        self.brand_label.setObjectName("brandLabel")
        self.brand_label.setAccessibleName("LockIn navigation")
        layout.addWidget(self.brand_label)
        self.collapse_button = IconButton("<", "Collapse sidebar", "Collapse")
        self.collapse_button.setObjectName("sidebarCollapseButton")
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        layout.addWidget(self.collapse_button)

        for definition in registry.definitions:
            if definition.page_id == "settings":
                layout.addStretch(1)
            button = QPushButton()
            button.setProperty("nav", True)
            button.setProperty("selected", False)
            button.setCheckable(True)
            button.setAccessibleName(f"Navigate to {definition.title}")
            button.clicked.connect(
                lambda checked=False, page_id=definition.page_id: self.page_requested.emit(page_id)
            )
            self._buttons[definition.page_id] = button
            layout.addWidget(button)
        self.set_collapsed(collapsed, emit_signal=False)

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    @property
    def buttons(self) -> MappingProxyType[str, QPushButton]:
        return MappingProxyType(self._buttons)

    def button_for(self, page_id: str) -> QPushButton:
        try:
            return self._buttons[page_id]
        except KeyError as exc:
            raise KeyError(f"Unknown sidebar page ID: {page_id}") from exc

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool, *, emit_signal: bool = True) -> None:
        changed = collapsed != self._collapsed
        self._collapsed = collapsed
        self.setFixedWidth(self.COLLAPSED_WIDTH if collapsed else self.EXPANDED_WIDTH)
        self.brand_label.setText("LI" if collapsed else "LOCKIN")
        self.collapse_button.setText(">" if collapsed else "<")
        self.collapse_button.setToolTip("Expand sidebar" if collapsed else "Collapse sidebar")
        for definition in self._registry.definitions:
            button = self._buttons[definition.page_id]
            button.setText(
                definition.symbol if collapsed else f"{definition.symbol}   {definition.title}"
            )
            button.setToolTip(definition.title if collapsed else "")
        if changed and emit_signal:
            self.collapsed_changed.emit(collapsed)

    def select_page(self, page_id: str) -> None:
        if page_id not in self._buttons:
            raise KeyError(f"Unknown sidebar page ID: {page_id}")
        for candidate_id, button in self._buttons.items():
            selected = candidate_id == page_id
            button.setChecked(selected)
            button.setProperty("selected", selected)
            button.style().unpolish(button)
            button.style().polish(button)
