"""Typed single source of truth for Phase 1 pages and their factories."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from PySide6.QtWidgets import QWidget

from app.analytics.analytics_service import AnalyticsService
from app.analytics.export_service import StatisticsExportService
from app.analytics.history_service import HistoryService
from app.audio.completion_sound import CompletionSoundService
from app.dashboard.dashboard_service import DashboardService
from app.quotes.quote_store import QuoteStore
from app.services.category_service import CategoryService
from app.services.daily_goal_service import DailyGoalService
from app.services.focus_session_coordinator import FocusSessionCoordinator
from app.services.portable_preview_service import PortablePreviewService
from app.services.portable_sync_coordinator import PortableSyncCoordinator
from app.services.session_aggregate_service import SessionAggregateService
from app.services.settings_service import SettingsService
from app.services.shortcut_settings_service import ShortcutSettingsService
from app.themes.theme_service import ThemeService
from app.ui.navigation import UnknownPageError
from app.ui.pages import (
    CategoriesPage,
    FocusSetupPage,
    HistoryPage,
    HomePage,
    QuotesPage,
    SettingsPage,
    StatisticsPage,
)

PageFactory = Callable[[], QWidget]


@dataclass(frozen=True)
class PageDefinition:
    page_id: str
    title: str
    description: str
    order: int
    symbol: str
    factory: PageFactory


class PageRegistry:
    def __init__(self, definitions: Iterable[PageDefinition]) -> None:
        ordered = sorted(definitions, key=lambda definition: definition.order)
        by_id: dict[str, PageDefinition] = {}
        orders: set[int] = set()
        for definition in ordered:
            if definition.page_id in by_id:
                raise ValueError(f"Duplicate page ID: {definition.page_id}")
            if definition.order in orders:
                raise ValueError(f"Duplicate page order: {definition.order}")
            by_id[definition.page_id] = definition
            orders.add(definition.order)
        self._definitions = tuple(ordered)
        self._by_id = MappingProxyType(by_id)

    @property
    def definitions(self) -> tuple[PageDefinition, ...]:
        return self._definitions

    @property
    def page_ids(self) -> tuple[str, ...]:
        return tuple(definition.page_id for definition in self._definitions)

    def get(self, page_id: str) -> PageDefinition:
        try:
            return self._by_id[page_id]
        except KeyError as exc:
            raise UnknownPageError(page_id) from exc

    def create(self, page_id: str) -> QWidget:
        return self.get(page_id).factory()


def build_page_registry(
    preview_service: PortablePreviewService,
    category_service: CategoryService,
    focus_session_coordinator: FocusSessionCoordinator,
    settings: SettingsService,
    shortcut_settings: ShortcutSettingsService,
    theme_service: ThemeService,
    runtime_root: Path,
    portable_root: Path,
    session_aggregates: SessionAggregateService | None = None,
    portable_sync: PortableSyncCoordinator | None = None,
    quote_store: QuoteStore | None = None,
    completion_sound: CompletionSoundService | None = None,
    dashboard: DashboardService | None = None,
    daily_goals: DailyGoalService | None = None,
    analytics: AnalyticsService | None = None,
    history: HistoryService | None = None,
    statistics_exporter: StatisticsExportService | None = None,
) -> PageRegistry:
    managed_quotes = quote_store or QuoteStore(
        portable_root / "quotes.csv", runtime_root / "quote_backups"
    )
    return PageRegistry(
        (
            PageDefinition(
                "home",
                "Home",
                "Motivational daily focus dashboard",
                0,
                "H",
                lambda: HomePage(dashboard, daily_goals),
            ),
            PageDefinition(
                "focus_setup",
                "Start Focus",
                "Real setup and locally saved black focus experience",
                1,
                "F",
                lambda: FocusSetupPage(
                    category_service,
                    settings,
                    focus_session_coordinator,
                ),
            ),
            PageDefinition(
                "statistics",
                "Statistics",
                "Complete local focus analytics",
                2,
                "S",
                lambda: StatisticsPage(analytics, history, statistics_exporter),
            ),
            PageDefinition(
                "history",
                "Session History",
                "Recent local sessions",
                3,
                "Y",
                lambda: HistoryPage(session_aggregates, history),
            ),
            PageDefinition(
                "categories",
                "Categories",
                "Permanent category management",
                4,
                "C",
                lambda: CategoriesPage(category_service),
            ),
            PageDefinition(
                "quotes",
                "Quotes",
                "Local quote management",
                5,
                "Q",
                lambda: QuotesPage(managed_quotes),
            ),
            PageDefinition(
                "settings",
                "Settings",
                "Desktop-shell preferences",
                6,
                "G",
                lambda: SettingsPage(
                    settings,
                    shortcut_settings,
                    theme_service,
                    runtime_root=runtime_root,
                    portable_root=portable_root,
                    portable_sync=portable_sync,
                    completion_sound=completion_sound,
                ),
            ),
        )
    )
