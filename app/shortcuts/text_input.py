"""Reusable suppression helper for shortcut-safe text entry."""

from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QKeySequenceEdit,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)


def is_editable_text_widget(widget: QWidget | None) -> bool:
    """Return True for Qt text editors and explicitly marked editing surfaces."""
    current = widget
    while current is not None:
        if isinstance(
            current,
            (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QKeySequenceEdit),
        ):
            return True
        if isinstance(current, QComboBox) and current.isEditable():
            return True
        if bool(current.property("lockinTextEditing")):
            return True
        current = current.parentWidget()
    return False
