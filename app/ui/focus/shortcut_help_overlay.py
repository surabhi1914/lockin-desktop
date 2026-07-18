"""Current enabled focus-shortcut mapping shown over the black focus view."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.shortcuts.bindings import ShortcutBinding
from app.shortcuts.registry import ShortcutRegistry
from app.ui.focus.focus_style import enforce_black_background


class ShortcutHelpOverlay(QWidget):
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("shortcutHelpOverlay")
        enforce_black_background(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 48, 64, 48)
        layout.addStretch(1)
        title = QLabel("FOCUS SHORTCUTS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = title.font()
        title_font.setPixelSize(38)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        self.mapping_layout = QFormLayout()
        self.mapping_layout.setHorizontalSpacing(32)
        layout.addLayout(self.mapping_layout)
        note = QLabel("These shortcuts work only while this LockIn focus screen is active.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setWordWrap(True)
        layout.addWidget(note)
        self.close_button = QPushButton("Close")
        self.close_button.setAccessibleName("Close focus shortcut help")
        self.close_button.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

    def present(
        self,
        registry: ShortcutRegistry,
        bindings: tuple[ShortcutBinding, ...],
    ) -> None:
        while self.mapping_layout.rowCount():
            self.mapping_layout.removeRow(0)
        by_id = {binding.action_id: binding for binding in bindings}
        for definition in registry.definitions:
            binding = by_id[definition.action_id]
            if not binding.enabled:
                continue
            key = QLabel(binding.display_text)
            key.setObjectName(f"shortcutHelpKey_{definition.action_id.value}")
            description = QLabel(definition.name)
            description.setObjectName(f"shortcutHelpAction_{definition.action_id.value}")
            self.mapping_layout.addRow(key, description)
