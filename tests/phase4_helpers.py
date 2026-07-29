"""Shared isolated Phase 4 focus-experience construction."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.audio.completion_sound import CompletionSoundService
from app.models.focus_session_draft import FocusSessionDraft
from app.services.distraction_marker_service import DistractionMarkerService
from app.services.focus_experience_service import FocusExperienceService
from app.services.focus_quote_service import FocusQuoteService
from app.services.focus_session_coordinator import FocusSessionCoordinator
from app.services.focus_window_service import FocusWindowService
from app.services.portable_preview_service import PortablePreviewService
from app.services.settings_service import SettingsService
from app.services.shortcut_settings_service import ShortcutSettingsService
from app.services.tray_service import TrayService
from app.themes.theme_service import ThemeService
from app.timer import ManualClock
from app.ui.focus.focus_dialogs import ExitDecision, StopDecision
from app.ui.focus.focus_experience import FocusExperience
from app.ui.focus.start_ritual import RitualDurations
from app.ui.main_window import MainWindow
from app.ui.page_registry import build_page_registry
from app.ui.pages.focus_setup_page import FocusSetupPage
from tests.phase3_helpers import isolated_category_service, path_config


@dataclass
class Phase4Harness:
    clock: ManualClock
    connection: object
    shortcut_settings: ShortcutSettingsService
    distractions: DistractionMarkerService
    coordinator: FocusSessionCoordinator
    experience: FocusExperience
    service: FocusExperienceService
    window_service: FocusWindowService
    tray: TrayService
    window: MainWindow
    setup: FocusSetupPage
    portable_root: Path

    def close(self) -> None:
        self.service.shutdown()
        self.coordinator.shutdown()
        self.tray.dispose()
        self.window.hide()
        self.connection.close()  # type: ignore[attr-defined]


def build_phase4_harness(
    qapp: QApplication,
    tmp_path: Path,
    *,
    tray_available: bool = False,
    stop_decision: StopDecision = StopDecision.STOP_AND_REVIEW,
    exit_decision: ExitDecision = ExitDecision.KEEP_FOCUSING,
    completion_sound: CompletionSoundService | None = None,
) -> Phase4Harness:
    config = path_config(tmp_path)
    categories, connection, _ = isolated_category_service(config)
    clock = ManualClock()
    coordinator = FocusSessionCoordinator(categories, clock_factory=lambda: clock)
    settings = SettingsService(
        QSettings(str(tmp_path / "phase4-settings.ini"), QSettings.Format.IniFormat)
    )
    shortcut_settings = ShortcutSettingsService(settings.qsettings)
    preview = PortablePreviewService(config.portable_root)
    registry = build_page_registry(
        preview,
        categories,
        coordinator,
        settings,
        shortcut_settings,
        ThemeService(qapp),
        config.runtime_root,
        config.portable_root,
    )
    window = MainWindow(registry, settings)
    setup = window.page("focus_setup")
    assert isinstance(setup, FocusSetupPage)
    experience = FocusExperience(
        inactivity_ms=15,
        ritual_durations=RitualDurations(1, 1, 1, 0),
        reduced_motion=True,
    )
    window.install_focus_widget(experience)
    window_service = FocusWindowService(window)
    tray = TrayService(window, available_override=tray_available)
    distractions = DistractionMarkerService()
    service = FocusExperienceService(
        window,
        setup,
        coordinator,
        experience,
        window_service,
        tray,
        FocusQuoteService(preview, selector=lambda quotes: quotes[0]),
        shortcut_settings,
        distractions,
        completion_sound=completion_sound,
        stop_decision_provider=lambda: stop_decision,
        exit_decision_provider=lambda _available: exit_decision,
    )
    setup.set_focus_start_handler(service.start_focus)
    return Phase4Harness(
        clock=clock,
        connection=connection,
        shortcut_settings=shortcut_settings,
        distractions=distractions,
        coordinator=coordinator,
        experience=experience,
        service=service,
        window_service=window_service,
        tray=tray,
        window=window,
        setup=setup,
        portable_root=config.portable_root,
    )


def focus_draft(
    harness: Phase4Harness,
    *,
    duration: int = 60,
    ritual: bool = False,
    full_screen: bool = False,
    quotes: bool = True,
    sound: bool = False,
    overtime: bool = True,
    intention: str | None = "Do the important thing",
) -> FocusSessionDraft:
    category = harness.setup.category_selector.selected_category()
    assert category is not None
    return FocusSessionDraft(
        duration,
        category.category_id,
        category.category_name,
        intention,
        full_screen,
        quotes,
        sound,
        overtime,
        ritual,
        10,
    )
