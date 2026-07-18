"""PySide6 application composition, startup validation, and coordinated shutdown."""

import os
import sqlite3
import sys
from dataclasses import dataclass

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.analytics.analytics_service import AnalyticsService
from app.analytics.export_service import StatisticsExportService
from app.analytics.history_service import HistoryService
from app.audio.completion_sound import CompletionSoundService
from app.bootstrap import run_phase0_bootstrap
from app.core.errors import LockInError
from app.core.paths import PathConfig
from app.core.resources import ResourceLocator
from app.dashboard.dashboard_service import DashboardService
from app.database.connection import connect_database
from app.database.repositories.category_repository import CategoryRepository
from app.database.repositories.device_repository import DeviceRepository
from app.database.repositories.runtime_state_repository import RuntimeStateRepository
from app.database.repositories.session_repository import SessionRepository
from app.database.unit_of_work import UnitOfWork
from app.models.errors import CategoryError
from app.portability.category_portable_store import CategoryPortableStore
from app.quotes.quote_store import QuoteStore
from app.recovery.recovery_service import RecoveryService
from app.recovery.sleep_detector import PowerEventSource, SleepDetector
from app.recovery.windows_power_event_filter import WindowsPowerEventFilter
from app.services.application_import_service import ApplicationImportService
from app.services.category_service import CategoryService
from app.services.daily_goal_service import DailyGoalService
from app.services.data_location_service import DataLocationService
from app.services.device_identity_service import DeviceIdentityService
from app.services.distraction_marker_service import DistractionMarkerService
from app.services.focus_experience_service import FocusExperienceService
from app.services.focus_quote_service import FocusQuoteService
from app.services.focus_session_coordinator import FocusSessionCoordinator
from app.services.focus_window_service import FocusWindowService
from app.services.new_device_setup_service import NewDeviceSetupService
from app.services.portable_preview_service import PortablePreviewService
from app.services.portable_sync_coordinator import PortableSyncCoordinator
from app.services.portable_sync_service import PortableSyncService
from app.services.portable_verification_service import PortableVerificationService
from app.services.session_aggregate_service import SessionAggregateService
from app.services.session_persistence_service import SessionPersistenceService
from app.services.settings_service import CloseBehavior, SettingsService
from app.services.shortcut_settings_service import ShortcutSettingsService
from app.services.tray_service import TrayService
from app.services.unfinished_detector_service import UnfinishedDetectorService, UnfinishedSession
from app.themes.theme_registry import ThemeRegistry
from app.themes.theme_service import ThemeLoadError, ThemeService
from app.ui.dialogs.import_preview_dialog import ImportPreviewDialog
from app.ui.dialogs.recovery_dialog import RecoveredSessionReviewDialog, RecoveryDialog
from app.ui.dialogs.select_portable_data_dialog import select_portable_data_folder
from app.ui.focus.focus_experience import FocusExperience
from app.ui.main_window import MainWindow
from app.ui.page_registry import PageRegistry, build_page_registry
from app.ui.pages.focus_setup_page import FocusSetupPage
from app.ui.pages.settings_page import SettingsPage


class ApplicationStartupError(RuntimeError):
    """Raised when the desktop shell cannot start without risking user data."""


class ShutdownCoordinator:
    """One owner for UI persistence, database closure, tray disposal, and explicit exit."""

    def __init__(
        self,
        application: QApplication,
        window: MainWindow,
        settings: SettingsService,
        connection: sqlite3.Connection,
        tray_service: TrayService,
        focus_session_coordinator: FocusSessionCoordinator,
        focus_experience_service: FocusExperienceService,
        portable_sync: PortableSyncCoordinator | None = None,
        power_event_filter: WindowsPowerEventFilter | None = None,
    ) -> None:
        self._application = application
        self._window = window
        self._settings = settings
        self._connection = connection
        self._tray_service = tray_service
        self._focus_session_coordinator = focus_session_coordinator
        self._focus_experience_service = focus_experience_service
        self._portable_sync = portable_sync
        self._power_event_filter = power_event_filter
        self._explicit_exit = False
        self._exit_requested = False
        self._shutdown_complete = False
        self._application.aboutToQuit.connect(self.shutdown)

    @property
    def shutdown_complete(self) -> bool:
        return self._shutdown_complete

    def handle_close_request(self) -> bool:
        if self._explicit_exit:
            return True
        if self._focus_experience_service.has_active_session:
            if not self._focus_experience_service.request_close():
                self._exit_requested = False
                return False
            self._explicit_exit = True
            QTimer.singleShot(0, self._application.quit)
            return True
        if self._exit_requested:
            self._explicit_exit = True
            QTimer.singleShot(0, self._application.quit)
            return True
        should_hide = (
            self._settings.minimize_to_tray()
            and self._settings.close_behavior() == CloseBehavior.MINIMIZE_TO_TRAY
            and self._tray_service.available
        )
        if should_hide:
            self._tray_service.hide_window(inform_once=True)
            return False
        self._explicit_exit = True
        QTimer.singleShot(0, self._application.quit)
        return True

    def request_exit(self) -> None:
        self._exit_requested = True
        self._window.close()

    def shutdown(self) -> None:
        if self._shutdown_complete:
            return
        self._focus_experience_service.shutdown()
        if self._portable_sync is not None:
            self._portable_sync.stop()
        if self._power_event_filter is not None:
            self._power_event_filter.dispose()
        self._window.save_ui_state()
        self._focus_session_coordinator.shutdown()
        self._settings.sync()
        self._tray_service.dispose()
        self._connection.close()
        self._shutdown_complete = True


@dataclass(frozen=True)
class ApplicationContext:
    application: QApplication
    config: PathConfig
    connection: sqlite3.Connection
    settings: SettingsService
    theme_service: ThemeService
    preview_service: PortablePreviewService
    category_service: CategoryService
    shortcut_settings_service: ShortcutSettingsService
    distraction_marker_service: DistractionMarkerService
    device_id: str
    session_persistence_service: SessionPersistenceService
    session_aggregate_service: SessionAggregateService
    portable_sync: PortableSyncCoordinator
    recovery_service: RecoveryService
    sleep_detector: SleepDetector
    power_event_filter: WindowsPowerEventFilter
    completion_sound: CompletionSoundService
    quote_store: QuoteStore
    daily_goal_service: DailyGoalService
    dashboard_service: DashboardService
    analytics_service: AnalyticsService
    history_service: HistoryService
    statistics_exporter: StatisticsExportService
    application_import_service: ApplicationImportService
    unfinished_sessions: tuple[UnfinishedSession, ...]
    focus_session_coordinator: FocusSessionCoordinator
    focus_experience: FocusExperience
    focus_window_service: FocusWindowService
    focus_experience_service: FocusExperienceService
    page_registry: PageRegistry
    window: MainWindow
    tray_service: TrayService
    shutdown_coordinator: ShutdownCoordinator

    def shutdown(self) -> None:
        self.shutdown_coordinator.shutdown()


def _application_instance(argv: list[str]) -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        if not isinstance(existing, QApplication):
            raise ApplicationStartupError("An incompatible Qt application instance already exists")
        application = existing
    else:
        application = QApplication(["lockin", *argv])
    application.setOrganizationName(SettingsService.ORGANIZATION)
    application.setApplicationName(SettingsService.APPLICATION)
    application.setApplicationDisplayName("LockIn")
    icon = ResourceLocator.standard().optional("app", "assets", "icons", "lockin.ico")
    if icon is not None:
        application.setWindowIcon(QIcon(str(icon)))
    return application


def create_application(
    argv: list[str] | None = None,
    *,
    config: PathConfig | None = None,
    settings: SettingsService | None = None,
    theme_registry: ThemeRegistry | None = None,
    tray_available: bool | None = None,
    show_window: bool = False,
) -> ApplicationContext:
    """Create a complete testable Phase 4 context without entering the Qt event loop."""
    arguments = argv or []
    application = _application_instance(arguments)
    settings_service = settings or SettingsService()
    resolved = config or PathConfig.from_environment()
    selected_portable = DataLocationService(settings_service.qsettings).selected()
    if (
        config is None
        and "LOCKIN_PORTABLE_ROOT" not in os.environ
        and selected_portable is not None
    ):
        resolved = PathConfig(resolved.repository_root, resolved.runtime_root, selected_portable)
    bootstrap = run_phase0_bootstrap(config=resolved)
    if not bootstrap.success:
        raise ApplicationStartupError("; ".join(bootstrap.errors))
    connection = connect_database(resolved.database_path)
    try:
        device_id = DeviceIdentityService(
            settings_service.qsettings,
            DeviceRepository(connection),
            UnitOfWork(connection),
        ).ensure()
        shortcut_settings_service = ShortcutSettingsService(settings_service.qsettings)
        distraction_marker_service = DistractionMarkerService()
        theme_service = ThemeService(application, theme_registry)
        theme_service.apply_saved(settings_service)
        preview_service = PortablePreviewService(resolved.portable_root)
        category_repository = CategoryRepository(connection)
        category_store = CategoryPortableStore(
            resolved.portable_root / "categories.csv",
            backup_directory=resolved.runtime_root / "category_backups",
        )
        category_service = CategoryService(
            category_repository,
            category_store,
            recovery_marker_path=resolved.runtime_root / "category_recovery_required.txt",
        )
        category_service.initialize()
        portable_service = PortableSyncService(
            connection,
            resolved.portable_root,
            resolved.runtime_root / "portable_backups",
        )
        portable_verifier = PortableVerificationService(
            connection,
            resolved.portable_root,
            resolved.runtime_root / "portable_backups",
        )
        portable_sync = PortableSyncCoordinator(connection, portable_service, portable_verifier)
        recovery_service = RecoveryService(
            connection,
            post_recovery_sync=portable_sync.sync_session,
        )
        power_source = PowerEventSource()
        sleep_detector = SleepDetector(power_source)
        power_event_filter = WindowsPowerEventFilter(power_source)
        power_event_filter.install(application)
        session_persistence_service = SessionPersistenceService(
            connection,
            device_id,
            post_finalize_sync=portable_sync.sync_session,
        )
        session_aggregate_service = session_persistence_service.aggregates
        unfinished_sessions = UnfinishedDetectorService(
            RuntimeStateRepository(connection), SessionRepository(connection)
        ).detect()
        if unfinished_sessions:
            session_persistence_service.block_new_sessions(
                "An unfinished local session was detected. Resolve its confirmed-time "
                "recovery before starting another session."
            )
        focus_session_coordinator = FocusSessionCoordinator(category_service)
        completion_sound = CompletionSoundService(
            settings_service,
            ResourceLocator.standard().required("app", "assets", "lockin_completion.wav"),
        )
        quote_store = QuoteStore(
            resolved.portable_root / "quotes.csv",
            resolved.runtime_root / "quote_backups",
        )
        daily_goal_service = DailyGoalService(
            connection,
            resolved.portable_root / "daily_goals.csv",
            resolved.runtime_root / "goal_backups",
        )
        dashboard_service = DashboardService(connection)
        analytics_service = AnalyticsService(connection, current_device_id=device_id)
        history_service = HistoryService(connection)
        statistics_exporter = StatisticsExportService(resolved.portable_root)
        page_registry = build_page_registry(
            preview_service,
            category_service,
            focus_session_coordinator,
            settings_service,
            shortcut_settings_service,
            theme_service,
            resolved.runtime_root,
            resolved.portable_root,
            session_aggregate_service,
            portable_sync,
            quote_store,
            completion_sound,
            dashboard_service,
            daily_goal_service,
            analytics_service,
            history_service,
            statistics_exporter,
        )
        window = MainWindow(page_registry, settings_service)
        window.configure_about(resolved.runtime_root, resolved.portable_root)
        tray_service = TrayService(window, available_override=tray_available)
        setup_page = window.page("focus_setup")
        if not isinstance(setup_page, FocusSetupPage):
            raise ApplicationStartupError("focus setup page has an unexpected type")
        focus_experience = FocusExperience()
        window.install_focus_widget(focus_experience)
        focus_window_service = FocusWindowService(window)
        focus_experience_service = FocusExperienceService(
            window,
            setup_page,
            focus_session_coordinator,
            focus_experience,
            focus_window_service,
            tray_service,
            FocusQuoteService(preview_service),
            shortcut_settings_service,
            distraction_marker_service,
            persistence_service=session_persistence_service,
            recovery_service=recovery_service,
            sleep_detector=sleep_detector,
            completion_sound=completion_sound,
        )
        setup_page.set_focus_start_handler(focus_experience_service.start_focus)
        coordinator = ShutdownCoordinator(
            application,
            window,
            settings_service,
            connection,
            tray_service,
            focus_session_coordinator,
            focus_experience_service,
            portable_sync,
            power_event_filter,
        )
        tray_service.set_exit_callback(coordinator.request_exit)
        window.set_close_request_handler(coordinator.handle_close_request)
        application.setQuitOnLastWindowClosed(not tray_service.available)
        settings_page = window.page("settings")
        if not isinstance(settings_page, SettingsPage):
            raise ApplicationStartupError("settings page has an unexpected type")
        application_import_service = ApplicationImportService(
            window,
            resolved.runtime_root,
            resolved.database_path,
            connection,
            settings_service,
            has_active_session=lambda: focus_experience_service.has_active_session,
            close_application_services=coordinator.shutdown,
            quit_application=application.quit,
        )
        settings_page.set_portable_import_handler(application_import_service.request_import)
        context = ApplicationContext(
            application=application,
            config=resolved,
            connection=connection,
            settings=settings_service,
            theme_service=theme_service,
            preview_service=preview_service,
            category_service=category_service,
            shortcut_settings_service=shortcut_settings_service,
            distraction_marker_service=distraction_marker_service,
            device_id=device_id,
            session_persistence_service=session_persistence_service,
            session_aggregate_service=session_aggregate_service,
            portable_sync=portable_sync,
            recovery_service=recovery_service,
            sleep_detector=sleep_detector,
            power_event_filter=power_event_filter,
            completion_sound=completion_sound,
            quote_store=quote_store,
            daily_goal_service=daily_goal_service,
            dashboard_service=dashboard_service,
            analytics_service=analytics_service,
            history_service=history_service,
            statistics_exporter=statistics_exporter,
            application_import_service=application_import_service,
            unfinished_sessions=unfinished_sessions,
            focus_session_coordinator=focus_session_coordinator,
            focus_experience=focus_experience,
            focus_window_service=focus_window_service,
            focus_experience_service=focus_experience_service,
            page_registry=page_registry,
            window=window,
            tray_service=tray_service,
            shutdown_coordinator=coordinator,
        )
        if show_window:
            window.show()
        portable_sync.start()
        return context
    except (OSError, RuntimeError, ValueError, KeyError, CategoryError, sqlite3.Error) as exc:
        connection.close()
        if isinstance(exc, ApplicationStartupError):
            raise
        raise ApplicationStartupError(str(exc)) from exc


def run(argv: list[str] | None = None) -> int:
    arguments = argv or []
    onboarding = _offer_new_device_onboarding(arguments)
    if onboarding is False:
        return 0
    if onboarding is None:
        return 1
    try:
        context = create_application(arguments, show_window=False)
    except (ApplicationStartupError, LockInError, ThemeLoadError, OSError, sqlite3.Error) as exc:
        message = f"LockIn could not start safely: {exc}"
        print(message, file=sys.stderr)
        try:
            application = _application_instance(arguments)
            QMessageBox.critical(None, "LockIn startup error", message)
            application.quit()
        except ApplicationStartupError:
            pass
        return 1
    if context.unfinished_sessions:
        for analysis in context.recovery_service.analyses():
            while True:
                choice = RecoveryDialog(analysis).exec()
                if choice == RecoveryDialog.REVIEW:
                    RecoveredSessionReviewDialog(analysis).exec()
                    continue
                if choice == RecoveryDialog.SAVE_CONFIRMED:
                    result = context.recovery_service.save_confirmed(analysis.session_id)
                    QMessageBox.information(None, "Recovery saved", result.message)
                    break
                if choice == RecoveryDialog.DISCARD:
                    result = context.recovery_service.discard(analysis.session_id)
                    QMessageBox.information(None, "Session discarded", result.message)
                    break
                context.shutdown()
                return 0
        context.session_persistence_service.clear_block()
    context.window.show()
    exit_code = context.application.exec()
    context.shutdown()
    return exit_code


def _offer_new_device_onboarding(arguments: list[str]) -> bool | None:
    config = PathConfig.from_environment()
    if not NewDeviceSetupService.runtime_is_empty(config.runtime_root):
        return True
    if not list(config.portable_root.glob("sessions/*/*.csv")):
        return True
    application = _application_instance(arguments)
    settings = SettingsService()
    choice = QMessageBox.question(
        None,
        "Set Up LockIn on This Device",
        "Existing portable history is available. Use it to build the local database on this "
        "device?\n\nNo starts with an empty local history. Git remains manual.",
        QMessageBox.StandardButton.Yes
        | QMessageBox.StandardButton.No
        | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Yes,
    )
    if choice == QMessageBox.StandardButton.Cancel:
        return False
    if choice == QMessageBox.StandardButton.No:
        return True
    selected = select_portable_data_folder(None, config.portable_root)
    if selected is None:
        return False
    setup = NewDeviceSetupService(settings.qsettings)
    report = setup.verify(selected, config.runtime_root)
    if not report.safe:
        QMessageBox.warning(
            None,
            "Portable data is not ready",
            "\n".join(report.errors)
            or "Resolve the reported conflicts before rebuilding this device.",
        )
        return None
    if ImportPreviewDialog(report).exec() != QDialog.DialogCode.Accepted:
        return False
    result = setup.rebuild(selected, config.runtime_root)
    if not result.success:
        QMessageBox.critical(None, "Device setup failed", "\n".join(result.errors))
        return None
    QMessageBox.information(
        None,
        "Device setup complete",
        f"Imported {result.inserted} record(s). New local device: "
        f"{result.local_device_id[:8] if result.local_device_id else '-'}.",
    )
    application.processEvents()
    return True


if __name__ == "__main__":
    raise SystemExit(run())
