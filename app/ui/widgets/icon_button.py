"""Keyboard-focusable text-symbol button used where no icon pack is needed."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton, QWidget


class IconButton(QToolButton):
    def __init__(
        self, symbol: str, tooltip: str, fallback_text: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._symbol = symbol
        self._fallback_text = fallback_text
        self.setText(symbol or fallback_text)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAutoRaise(False)

    def use_fallback_text(self, enabled: bool) -> None:
        self.setText(self._fallback_text if enabled and self._fallback_text else self._symbol)
