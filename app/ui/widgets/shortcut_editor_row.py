"""One staged focus-shortcut editor row."""

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.shortcuts.actions import ShortcutActionDefinition
from app.shortcuts.bindings import ShortcutBinding
from app.shortcuts.validator import ShortcutValidator


class ShortcutEditorRow(QWidget):
    changed = Signal()
    reset_requested = Signal(object)

    def __init__(
        self,
        definition: ShortcutActionDefinition,
        validator: ShortcutValidator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.definition = definition
        self._validator = validator
        self.setObjectName(f"shortcutRow_{definition.action_id.value}")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 5, 0, 5)
        outer.setSpacing(4)
        top = QHBoxLayout()
        self.enabled_checkbox = QCheckBox(definition.name)
        self.enabled_checkbox.setObjectName(f"shortcutEnabled_{definition.action_id.value}")
        self.sequence_edit = QKeySequenceEdit()
        self.sequence_edit.setObjectName(f"shortcutSequence_{definition.action_id.value}")
        self.sequence_edit.setMaximumSequenceLength(1)
        self.sequence_edit.setClearButtonEnabled(True)
        self.sequence_edit.setAccessibleName(f"Shortcut for {definition.name}")
        self.reset_button = QPushButton("Reset")
        self.reset_button.setObjectName(f"shortcutReset_{definition.action_id.value}")
        top.addWidget(self.enabled_checkbox)
        top.addStretch(1)
        top.addWidget(self.sequence_edit)
        top.addWidget(self.reset_button)
        outer.addLayout(top)
        self.description_label = QLabel(definition.description)
        self.description_label.setWordWrap(True)
        self.description_label.setProperty("muted", True)
        outer.addWidget(self.description_label)
        self.enabled_checkbox.toggled.connect(self._enabled_changed)
        self.sequence_edit.keySequenceChanged.connect(lambda _sequence: self.changed.emit())
        self.reset_button.clicked.connect(
            lambda: self.reset_requested.emit(self.definition.action_id)
        )

    def set_binding(self, binding: ShortcutBinding) -> None:
        self.enabled_checkbox.blockSignals(True)
        self.sequence_edit.blockSignals(True)
        self.enabled_checkbox.setChecked(binding.enabled)
        self.sequence_edit.setKeySequence(
            QKeySequence.fromString(binding.key_sequence, QKeySequence.SequenceFormat.PortableText)
        )
        self.sequence_edit.setEnabled(binding.enabled)
        self.enabled_checkbox.blockSignals(False)
        self.sequence_edit.blockSignals(False)

    def staged_binding(self) -> ShortcutBinding:
        portable = self.sequence_edit.keySequence().toString(
            QKeySequence.SequenceFormat.PortableText
        )
        return self._validator.make_binding(
            self.definition.action_id,
            portable,
            self.enabled_checkbox.isChecked(),
        )

    def set_default(self) -> None:
        self.set_binding(self._validator.default_binding(self.definition.action_id))
        self.changed.emit()

    def _enabled_changed(self, enabled: bool) -> None:
        self.sequence_edit.setEnabled(enabled)
        self.changed.emit()
