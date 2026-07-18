"""Real focus setup with a replaceable Phase 4 experience handoff."""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.models.errors import (
    CategoryError,
    FocusSessionAlreadyActiveError,
    InvalidFocusSessionDraftError,
    NoActiveFocusSessionError,
    SessionPersistenceError,
)
from app.models.focus_session_draft import FocusSessionDraft
from app.services.category_service import OTHER_CATEGORY_ID, CategoryService
from app.services.focus_session_coordinator import FocusSessionContext, FocusSessionCoordinator
from app.services.settings_service import SettingsService
from app.timer.errors import TimerError
from app.timer.models import TimerSnapshot
from app.ui.widgets import (
    CategorySelector,
    DurationInput,
    PageHeader,
    SessionOptions,
    SessionOptionsPanel,
    ValidationMessage,
)


class FocusSetupPage(QWidget):
    """Collect real setup values and hand them to the persisted focus flow."""

    def __init__(
        self,
        category_service: CategoryService,
        settings: SettingsService,
        coordinator: FocusSessionCoordinator,
    ) -> None:
        super().__init__()
        self.setObjectName("page_focus_setup")
        self._category_service = category_service
        self._settings = settings
        self.coordinator = coordinator
        self._focus_start_handler: Callable[[FocusSessionDraft], object] = coordinator.start
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(0)
        self.stack = QStackedWidget()
        self.setup_widget = self._build_setup()
        self.preview_widget = self._build_preview()
        self.stack.addWidget(self.setup_widget)
        self.stack.addWidget(self.preview_widget)
        layout.addWidget(self.stack)
        self.coordinator.preview_started.connect(self._show_preview)
        self.coordinator.preview_ended.connect(self._return_to_setup)
        self.coordinator.snapshot_changed.connect(self._render_snapshot)
        self.duration_input.validity_changed.connect(self._validate_form)
        self.category_selector.validity_changed.connect(self._validate_form)
        self.category_selector.selection_changed.connect(self._validate_form)
        self.intention_input.textChanged.connect(self._validate_form)
        self._validate_form()

    def _build_setup(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(
            PageHeader(
                "Start Focus",
                "Set up the real black focus experience. Final sessions are saved locally.",
            )
        )
        form_group = QGroupBox("Focus-session setup")
        form = QFormLayout(form_group)
        hours, minutes = self._settings.focus_duration()
        self.duration_input = DurationInput(hours, minutes)
        form.addRow("Duration", self.duration_input)
        selected_id = self._initial_category_id()
        self.category_selector = CategorySelector(
            self._category_service,
            selected_category_id=selected_id,
        )
        form.addRow("Category", self.category_selector)
        self.intention_input = QLineEdit()
        self.intention_input.setObjectName("sessionIntentionInput")
        self.intention_input.setAccessibleName("Optional temporary session intention")
        self.intention_input.setPlaceholderText("Optional — up to 240 characters; never saved")
        self.intention_input.setMaxLength(500)
        form.addRow("Session intention — optional", self.intention_input)
        self.intention_count = QLabel("0 / 240")
        self.intention_count.setProperty("muted", True)
        form.addRow("", self.intention_count)
        options = SessionOptions(
            self._settings.focus_start_in_fullscreen(),
            self._settings.focus_show_quotes(),
            self._settings.focus_play_completion_sound(),
            self._settings.focus_overtime_enabled(),
            self._settings.focus_start_ritual_enabled(),
        )
        self.options_panel = SessionOptionsPanel(options)
        form.addRow("Session options", self.options_panel)
        grace = QLabel("10 seconds (fixed for Phase 4)")
        grace.setProperty("muted", True)
        form.addRow("Continuity grace", grace)
        layout.addWidget(form_group)
        self.form_validation = ValidationMessage()
        layout.addWidget(self.form_validation)
        self.start_button = QPushButton("Start Lock-In")
        self.start_button.setObjectName("startLockInButton")
        self.start_button.clicked.connect(self._start_preview)
        layout.addWidget(self.start_button)
        layout.addStretch(1)
        return page

    def _build_preview(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(
            PageHeader(
                "Timer status",
                "The active timer is saved through the Phase 6 lifecycle service.",
            )
        )
        status_group = QGroupBox("Running preview")
        status = QFormLayout(status_group)
        self.preview_category = QLabel("—")
        self.preview_remaining = QLabel("—")
        self.preview_state = QLabel("—")
        status.addRow("Category", self.preview_category)
        status.addRow("Remaining", self.preview_remaining)
        status.addRow("State", self.preview_state)
        layout.addWidget(status_group)
        self.intention_group = QGroupBox("Temporary intention — memory only")
        intention_layout = QVBoxLayout(self.intention_group)
        self.preview_intention = QLabel()
        self.preview_intention.setWordWrap(True)
        intention_layout.addWidget(self.preview_intention)
        layout.addWidget(self.intention_group)
        self.ritual_note = QLabel(
            "Start ritual selected. Phase 3 starts immediately; the full ritual arrives in Phase 4."
        )
        self.ritual_note.setProperty("muted", True)
        self.ritual_note.setWordWrap(True)
        layout.addWidget(self.ritual_note)
        controls = QHBoxLayout()
        self.pause_button = self._button("Pause", self._pause)
        self.resume_button = self._button("Resume", self._resume)
        self.overtime_button = self._button("Start Overtime", self._start_overtime)
        self.stop_button = self._button("Stop Preview", self._stop_preview)
        for button in (
            self.pause_button,
            self.resume_button,
            self.overtime_button,
            self.stop_button,
        ):
            controls.addWidget(button)
        controls.addStretch(1)
        layout.addLayout(controls)
        self.preview_validation = ValidationMessage()
        layout.addWidget(self.preview_validation)
        no_features = QLabel(
            "No full screen or other focus-screen features run in this fallback status view."
        )
        no_features.setProperty("muted", True)
        no_features.setWordWrap(True)
        layout.addWidget(no_features)
        layout.addStretch(1)
        return page

    @staticmethod
    def _button(text: str, callback: Callable[[], None]) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(callback)
        return button

    def _initial_category_id(self) -> str | None:
        requested = self._settings.focus_last_category_id()
        if requested is not None:
            try:
                self._category_service.resolve_selected_category(requested)
            except CategoryError:
                pass
            else:
                return requested
        try:
            self._category_service.resolve_selected_category(OTHER_CATEGORY_ID)
        except CategoryError:
            active = self._category_service.list_active()
            return active[0].category_id if active else None
        return OTHER_CATEGORY_ID

    def _validate_form(self, _value: object = None) -> None:
        intention_length = len(self.intention_input.text().strip())
        self.intention_count.setText(f"{intention_length} / 240")
        errors: list[str] = []
        if not self.duration_input.is_valid:
            errors.append("Choose a duration of at least one minute.")
        if not self.category_selector.is_valid:
            errors.append("Choose an active category.")
        if intention_length > 240:
            errors.append("Temporary intention cannot exceed 240 characters.")
        if errors:
            self.form_validation.set_error(" ".join(errors))
        else:
            self.form_validation.clear_error()
        self.start_button.setEnabled(not errors and not self.coordinator.has_active_preview)

    def build_draft(self) -> FocusSessionDraft:
        category = self.category_selector.selected_category()
        if category is None:
            raise InvalidFocusSessionDraftError("Choose an active category.")
        options = self.options_panel.options()
        return FocusSessionDraft(
            planned_duration_seconds=self.duration_input.duration_seconds(),
            category_id=category.category_id,
            category_name_snapshot=category.category_name,
            temporary_intention=self.intention_input.text(),
            start_in_fullscreen=options.start_in_fullscreen,
            show_quotes=options.show_quotes,
            play_completion_sound=options.play_completion_sound,
            overtime_enabled=options.overtime_enabled,
            start_ritual_enabled=options.start_ritual_enabled,
            pause_grace_seconds=10,
        )

    def set_focus_start_handler(self, handler: Callable[[FocusSessionDraft], object]) -> None:
        """Install the application-level focus controller after shell composition."""
        self._focus_start_handler = handler

    def clear_after_session(self) -> None:
        """Clear sensitive setup state when the Phase 4 experience ends."""
        self._return_to_setup()

    def _start_preview(self) -> None:
        try:
            draft = self.build_draft()
            self._remember_safe_defaults(draft)
            self._focus_start_handler(draft)
        except (
            CategoryError,
            InvalidFocusSessionDraftError,
            FocusSessionAlreadyActiveError,
            TimerError,
            SessionPersistenceError,
        ) as exc:
            self.form_validation.set_error(str(exc))

    def _remember_safe_defaults(self, draft: FocusSessionDraft) -> None:
        self._settings.set_focus_last_category_id(draft.category_id)
        self._settings.set_focus_duration(self.duration_input.hours, self.duration_input.minutes)
        self._settings.set_focus_start_in_fullscreen(draft.start_in_fullscreen)
        self._settings.set_focus_show_quotes(draft.show_quotes)
        self._settings.set_focus_play_completion_sound(draft.play_completion_sound)
        self._settings.set_focus_overtime_enabled(draft.overtime_enabled)
        self._settings.set_focus_start_ritual_enabled(draft.start_ritual_enabled)

    def _show_preview(self, value: object) -> None:
        if not isinstance(value, FocusSessionContext):
            return
        context = value
        self.preview_category.setText(context.draft.category_name_snapshot)
        intention = context.draft.temporary_intention
        self.intention_group.setVisible(intention is not None)
        self.preview_intention.setText(intention or "")
        self.ritual_note.setVisible(context.draft.start_ritual_enabled)
        self._render_snapshot(context.snapshot)
        self.stack.setCurrentWidget(self.preview_widget)

    def _render_snapshot(self, value: object) -> None:
        if not isinstance(value, TimerSnapshot):
            return
        snapshot = value
        self.preview_remaining.setText(f"{snapshot.remaining_planned_seconds} seconds")
        self.preview_state.setText(snapshot.state.value)
        self.pause_button.setEnabled(snapshot.can_pause)
        self.resume_button.setEnabled(snapshot.can_resume)
        self.stop_button.setEnabled(snapshot.can_stop)
        self.overtime_button.setEnabled(snapshot.can_start_overtime)

    def _pause(self) -> None:
        self._preview_action(self.coordinator.pause)

    def _resume(self) -> None:
        self._preview_action(self.coordinator.resume)

    def _start_overtime(self) -> None:
        self._preview_action(self.coordinator.start_overtime)

    def _stop_preview(self) -> None:
        self._preview_action(self.coordinator.stop_and_end)

    def _preview_action(self, action: Callable[[], object]) -> None:
        try:
            action()
        except (TimerError, NoActiveFocusSessionError) as exc:
            self.preview_validation.set_error(str(exc))
        else:
            self.preview_validation.clear_error()

    def _return_to_setup(self) -> None:
        self.intention_input.clear()
        self.stack.setCurrentWidget(self.setup_widget)
        self.category_selector.refresh()
        self._validate_form()
