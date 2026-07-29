"""Configurable options for a focus session."""

from dataclasses import dataclass

from PySide6.QtWidgets import QCheckBox, QFormLayout, QLabel, QVBoxLayout, QWidget


@dataclass(frozen=True, slots=True)
class SessionOptions:
    start_in_fullscreen: bool
    show_quotes: bool
    play_completion_sound: bool
    overtime_enabled: bool
    start_ritual_enabled: bool


class SessionOptionsPanel(QWidget):
    def __init__(
        self,
        options: SessionOptions | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        selected = options or SessionOptions(True, True, True, True, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.fullscreen_checkbox = QCheckBox("Start in full screen")
        self.quotes_checkbox = QCheckBox("Show quotes")
        self.sound_checkbox = QCheckBox("Play completion sound")
        self.overtime_checkbox = QCheckBox("Enable overtime")
        self.ritual_checkbox = QCheckBox("Use start ritual")
        self.fullscreen_checkbox.setChecked(selected.start_in_fullscreen)
        self.quotes_checkbox.setChecked(selected.show_quotes)
        self.sound_checkbox.setChecked(selected.play_completion_sound)
        self.sound_checkbox.setToolTip(
            "Play the local chime when planned focus completes. "
            "The global sound setting and volume also apply."
        )
        self.overtime_checkbox.setChecked(selected.overtime_enabled)
        self.ritual_checkbox.setChecked(selected.start_ritual_enabled)
        for checkbox in (
            self.fullscreen_checkbox,
            self.quotes_checkbox,
            self.sound_checkbox,
            self.overtime_checkbox,
            self.ritual_checkbox,
        ):
            form.addRow(checkbox)
        layout.addLayout(form)
        note = QLabel(
            "These choices apply to this session and are remembered for the next one. "
            "Completion sound also follows the global setting and volume."
        )
        note.setProperty("muted", True)
        note.setWordWrap(True)
        layout.addWidget(note)

    def options(self) -> SessionOptions:
        return SessionOptions(
            self.fullscreen_checkbox.isChecked(),
            self.quotes_checkbox.isChecked(),
            self.sound_checkbox.isChecked(),
            self.overtime_checkbox.isChecked(),
            self.ritual_checkbox.isChecked(),
        )
