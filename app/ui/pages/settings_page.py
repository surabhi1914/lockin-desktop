"""Desktop-shell preferences and staged device-local focus shortcuts."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.audio.completion_sound import CompletionSoundService
from app.services.portable_sync_coordinator import PortableSyncCoordinator
from app.services.settings_service import CloseBehavior, SettingsService, SidebarStartup
from app.services.shortcut_settings_service import ShortcutSettingsService
from app.shortcuts.actions import ShortcutActionId
from app.shortcuts.bindings import ShortcutBinding
from app.shortcuts.errors import ShortcutError
from app.themes.theme_service import ThemeService
from app.ui.dialogs.select_portable_data_dialog import select_portable_data_folder
from app.ui.widgets import PageHeader, ShortcutConflictMessage, ShortcutEditorRow

PortableImportHandler = Callable[[Path], None]


class SettingsPage(QWidget):
    def __init__(
        self,
        settings: SettingsService,
        shortcut_settings: ShortcutSettingsService,
        theme_service: ThemeService,
        runtime_root: Path,
        portable_root: Path,
        portable_sync: PortableSyncCoordinator | None = None,
        completion_sound: CompletionSoundService | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("page_settings")
        self._settings = settings
        self._shortcut_settings = shortcut_settings
        self._theme_service = theme_service
        self._portable_sync = portable_sync
        self._completion_sound = completion_sound
        self._portable_root = portable_root
        self._portable_import_handler: PortableImportHandler | None = None
        self.shortcut_rows: dict[ShortcutActionId, ShortcutEditorRow] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(
            PageHeader("Settings", "Appearance, desktop behavior, and local focus shortcuts.")
        )

        appearance = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance)
        self.theme_selector = QComboBox()
        self.theme_selector.setObjectName("themeSelector")
        for theme in theme_service.registry.themes:
            self.theme_selector.addItem(theme.display_name, theme.theme_id)
        appearance_form.addRow("Theme", self.theme_selector)
        layout.addWidget(appearance)

        behavior = QGroupBox("Window and sidebar")
        behavior_form = QFormLayout(behavior)
        self.sidebar_startup_selector = QComboBox()
        self.sidebar_startup_selector.addItem("Remember previous", SidebarStartup.REMEMBER.value)
        self.sidebar_startup_selector.addItem("Start expanded", SidebarStartup.EXPANDED.value)
        self.sidebar_startup_selector.addItem("Start collapsed", SidebarStartup.COLLAPSED.value)
        self.minimize_to_tray_checkbox = QCheckBox("Enable minimize-to-tray behavior")
        self.close_behavior_selector = QComboBox()
        self.close_behavior_selector.addItem("Exit application", CloseBehavior.EXIT.value)
        self.close_behavior_selector.addItem(
            "Minimize to tray", CloseBehavior.MINIMIZE_TO_TRAY.value
        )
        behavior_form.addRow("Sidebar startup", self.sidebar_startup_selector)
        behavior_form.addRow("Tray preference", self.minimize_to_tray_checkbox)
        behavior_form.addRow("Close behavior", self.close_behavior_selector)
        layout.addWidget(behavior)

        audio = QGroupBox("Completion sound")
        audio_form = QFormLayout(audio)
        self.sound_enabled_checkbox = QCheckBox("Play the local completion chime")
        self.sound_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.sound_volume_slider.setRange(0, 100)
        self.sound_volume_slider.setAccessibleName("Completion sound volume")
        self.sound_preview_button = QPushButton("Preview Sound")
        audio_form.addRow("Enabled", self.sound_enabled_checkbox)
        audio_form.addRow("Volume", self.sound_volume_slider)
        audio_form.addRow("", self.sound_preview_button)
        layout.addWidget(audio)

        storage = QGroupBox("Storage locations (read-only)")
        storage_form = QFormLayout(storage)
        self.runtime_path = QLineEdit(str(runtime_root))
        self.portable_path = QLineEdit(str(portable_root))
        self.runtime_path.setReadOnly(True)
        self.portable_path.setReadOnly(True)
        storage_form.addRow("Runtime", self.runtime_path)
        storage_form.addRow("Portable", self.portable_path)
        layout.addWidget(storage)

        sync_group = QGroupBox("Portable synchronization")
        sync_layout = QVBoxLayout(sync_group)
        self.sync_status_label = QLabel("Portable sync has not run in this launch.")
        self.sync_status_label.setWordWrap(True)
        sync_layout.addWidget(self.sync_status_label)
        sync_buttons = QHBoxLayout()
        self.sync_now_button = QPushButton("Sync now")
        self.sync_now_button.setObjectName("syncPortableNow")
        self.open_portable_button = QPushButton("Open portable folder")
        self.open_portable_button.setObjectName("openPortableFolder")
        self.use_portable_button = QPushButton("Use Existing Portable Data")
        self.use_portable_button.setObjectName("useExistingPortableData")
        self.import_history_button = QPushButton("Import Portable History")
        self.import_history_button.setObjectName("importPortableHistory")
        sync_buttons.addWidget(self.sync_now_button)
        sync_buttons.addWidget(self.open_portable_button)
        sync_buttons.addWidget(self.use_portable_button)
        sync_buttons.addWidget(self.import_history_button)
        sync_buttons.addStretch(1)
        sync_layout.addLayout(sync_buttons)
        layout.addWidget(sync_group)

        shortcut_group = QGroupBox("Focus shortcuts")
        shortcut_layout = QVBoxLayout(shortcut_group)
        local_note = QLabel(
            "Shortcuts work only while the LockIn focus screen is active. "
            "Every action can be disabled or reassigned."
        )
        local_note.setWordWrap(True)
        shortcut_layout.addWidget(local_note)
        for definition in self._shortcut_settings.registry.definitions:
            row = ShortcutEditorRow(definition, self._shortcut_settings.validator)
            row.changed.connect(self._validate_shortcuts)
            row.reset_requested.connect(self._reset_shortcut_row)
            self.shortcut_rows[definition.action_id] = row
            shortcut_layout.addWidget(row)
        self.shortcut_message = ShortcutConflictMessage()
        shortcut_layout.addWidget(self.shortcut_message)
        shortcut_buttons = QHBoxLayout()
        self.shortcut_apply_button = QPushButton("Apply")
        self.shortcut_apply_button.setObjectName("applyFocusShortcuts")
        self.shortcut_cancel_button = QPushButton("Cancel / Revert")
        self.shortcut_cancel_button.setObjectName("cancelFocusShortcuts")
        self.shortcut_reset_all_button = QPushButton("Reset All")
        self.shortcut_reset_all_button.setObjectName("resetAllFocusShortcuts")
        shortcut_buttons.addWidget(self.shortcut_apply_button)
        shortcut_buttons.addWidget(self.shortcut_cancel_button)
        shortcut_buttons.addWidget(self.shortcut_reset_all_button)
        shortcut_buttons.addStretch(1)
        shortcut_layout.addLayout(shortcut_buttons)
        layout.addWidget(shortcut_group)
        self.reset_button = QPushButton("Restore Phase 1 defaults")
        self.reset_button.setObjectName("resetPhase1Defaults")
        layout.addWidget(self.reset_button)
        layout.addStretch(1)
        self._connect()
        self.refresh()

    def _connect(self) -> None:
        self.theme_selector.currentIndexChanged.connect(self._theme_changed)
        self.sidebar_startup_selector.currentIndexChanged.connect(self._sidebar_startup_changed)
        self.minimize_to_tray_checkbox.toggled.connect(self._minimize_to_tray_changed)
        self.close_behavior_selector.currentIndexChanged.connect(self._close_behavior_changed)
        self.sound_enabled_checkbox.toggled.connect(self._sound_enabled_changed)
        self.sound_volume_slider.valueChanged.connect(self._sound_volume_changed)
        self.sound_preview_button.clicked.connect(self._preview_sound)
        self.reset_button.clicked.connect(self.restore_defaults)
        self.shortcut_apply_button.clicked.connect(self.apply_shortcuts)
        self.shortcut_cancel_button.clicked.connect(self.refresh_shortcuts)
        self.shortcut_reset_all_button.clicked.connect(self._confirm_reset_all_shortcuts)
        self._shortcut_settings.bindings_changed.connect(lambda _bindings: self.refresh_shortcuts())
        self.sync_now_button.clicked.connect(self._sync_now)
        self.open_portable_button.clicked.connect(self._open_portable_folder)
        self.use_portable_button.clicked.connect(self._request_portable_import)
        self.import_history_button.clicked.connect(self._request_portable_import)
        if self._portable_sync is not None:
            self._portable_sync.status_changed.connect(self._refresh_sync_status)

    def refresh(self) -> None:
        blockers = (
            QSignalBlocker(self.theme_selector),
            QSignalBlocker(self.sidebar_startup_selector),
            QSignalBlocker(self.minimize_to_tray_checkbox),
            QSignalBlocker(self.close_behavior_selector),
            QSignalBlocker(self.sound_enabled_checkbox),
            QSignalBlocker(self.sound_volume_slider),
        )
        self._set_combo(self.theme_selector, self._settings.theme_id())
        self._set_combo(self.sidebar_startup_selector, self._settings.sidebar_startup().value)
        self.minimize_to_tray_checkbox.setChecked(self._settings.minimize_to_tray())
        self._set_combo(self.close_behavior_selector, self._settings.close_behavior().value)
        self.sound_enabled_checkbox.setChecked(self._settings.completion_sound_enabled())
        self.sound_volume_slider.setValue(self._settings.completion_sound_volume())
        del blockers
        self.refresh_shortcuts()
        self._refresh_sync_status()

    def _sync_now(self) -> None:
        if self._portable_sync is None:
            self.sync_status_label.setText("Portable sync is unavailable.")
            return
        result = self._portable_sync.sync_all()
        detail = result.message
        if result.errors:
            detail += ": " + "; ".join(result.errors)
        self.sync_status_label.setText(detail)

    def _refresh_sync_status(self) -> None:
        if self._portable_sync is None or self._portable_sync.last_result is None:
            self.sync_status_label.setText("Portable sync has not run in this launch.")
            return
        result = self._portable_sync.last_result
        self.sync_status_label.setText(
            f"{result.message}. Last attempt: {result.completed_at_utc}. "
            f"Pending: {'yes' if self._portable_sync.pending else 'no'}."
        )

    def _open_portable_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._portable_root)))

    def set_portable_import_handler(self, handler: PortableImportHandler) -> None:
        self._portable_import_handler = handler

    def _request_portable_import(self) -> None:
        selected = select_portable_data_folder(self, self._portable_root)
        if selected is not None and self._portable_import_handler is not None:
            self._portable_import_handler(selected)

    def refresh_shortcuts(self) -> None:
        bindings = self._shortcut_settings.get_all()
        for binding in bindings:
            self.shortcut_rows[binding.action_id].set_binding(binding)
        if self._shortcut_settings.warnings:
            self.shortcut_message.show_message(" ".join(self._shortcut_settings.warnings))
        else:
            self.shortcut_message.clear_message()
        self.shortcut_apply_button.setEnabled(True)

    def staged_shortcuts(self) -> tuple[ShortcutBinding, ...]:
        return tuple(
            self.shortcut_rows[definition.action_id].staged_binding()
            for definition in self._shortcut_settings.registry.definitions
        )

    def apply_shortcuts(self) -> None:
        try:
            saved = self._shortcut_settings.save_all(self.staged_shortcuts())
        except ShortcutError as exc:
            self.shortcut_message.show_message(str(exc))
            self.shortcut_apply_button.setEnabled(False)
            return
        for binding in saved:
            self.shortcut_rows[binding.action_id].set_binding(binding)
        self.shortcut_message.clear_message()
        self.shortcut_apply_button.setEnabled(True)

    def _validate_shortcuts(self) -> None:
        try:
            self._shortcut_settings.validate(self.staged_shortcuts())
        except ShortcutError as exc:
            self.shortcut_message.show_message(str(exc))
            self.shortcut_apply_button.setEnabled(False)
        else:
            self.shortcut_message.clear_message()
            self.shortcut_apply_button.setEnabled(True)

    def _reset_shortcut_row(self, value: object) -> None:
        if not isinstance(value, (str, ShortcutActionId)):
            return
        try:
            action_id = ShortcutActionId(value)
        except ValueError:
            return
        self.shortcut_rows[action_id].set_default()

    def _confirm_reset_all_shortcuts(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset focus shortcuts?",
            "Restore all focus shortcuts to their enabled defaults?",
            QMessageBox.StandardButton.Reset | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer is not QMessageBox.StandardButton.Reset:
            return
        for row in self.shortcut_rows.values():
            row.set_default()
        self._validate_shortcuts()

    def restore_defaults(self) -> None:
        self._settings.reset_phase1_defaults()
        theme = self._theme_service.apply(self._settings.DEFAULT_THEME_ID)
        self._settings.set_theme_id(theme.theme_id)
        self.refresh()

    def _theme_changed(self) -> None:
        theme_id = str(self.theme_selector.currentData())
        theme = self._theme_service.apply(theme_id)
        self._settings.set_theme_id(theme.theme_id)

    def _sidebar_startup_changed(self) -> None:
        self._settings.set_sidebar_startup(
            SidebarStartup(str(self.sidebar_startup_selector.currentData()))
        )

    def _minimize_to_tray_changed(self, enabled: bool) -> None:
        self._settings.set_minimize_to_tray(enabled)

    def _close_behavior_changed(self) -> None:
        self._settings.set_close_behavior(
            CloseBehavior(str(self.close_behavior_selector.currentData()))
        )

    def _sound_enabled_changed(self, enabled: bool) -> None:
        self._settings.set_completion_sound_enabled(enabled)

    def _sound_volume_changed(self, volume: int) -> None:
        self._settings.set_completion_sound_volume(volume)

    def _preview_sound(self) -> None:
        if self._completion_sound is None or not self._completion_sound.preview():
            self.sync_status_label.setText(
                "Sound preview is unavailable. Timer completion will continue normally."
            )

    @staticmethod
    def _set_combo(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)
