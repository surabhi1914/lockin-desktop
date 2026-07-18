from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QKeySequenceEdit,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QTextEdit,
    QWidget,
)

from app.shortcuts.text_input import is_editable_text_widget


def test_every_required_editable_control_suppresses_shortcuts(qtbot: object) -> None:
    editable_combo = QComboBox()
    editable_combo.setEditable(True)
    widgets = [
        QLineEdit(),
        QTextEdit(),
        QPlainTextEdit(),
        QSpinBox(),
        QDoubleSpinBox(),
        editable_combo,
        QKeySequenceEdit(),
    ]
    for widget in widgets:
        qtbot.addWidget(widget)  # type: ignore[attr-defined]
        assert is_editable_text_widget(widget)
    marked_dialog_child = QWidget()
    marked_dialog_child.setProperty("lockinTextEditing", True)
    assert is_editable_text_widget(marked_dialog_child)
    plain_combo = QComboBox()
    assert not is_editable_text_widget(plain_combo)
