"""Motivational Home dashboard backed only by canonical dashboard metrics."""

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QDateEdit,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.dashboard.dashboard_service import DashboardService
from app.dashboard.models import DashboardSnapshot
from app.services.daily_goal_service import DailyGoalService
from app.ui.focus.focus_canvas import format_focus_time
from app.ui.widgets import EmptyState, MetricCard, PageHeader


class HomePage(QWidget):
    def __init__(
        self,
        dashboard: DashboardService | None = None,
        goals: DailyGoalService | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("page_home")
        self._dashboard = dashboard
        self._goals = goals
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        layout.addWidget(PageHeader("Home", "A focused view of today's momentum."))
        goal_group = QGroupBox("Daily focus goal")
        goal_form = QFormLayout(goal_group)
        self.goal_minutes = QSpinBox()
        self.goal_minutes.setRange(1, 10_080)
        self.goal_minutes.setValue(60)
        self.goal_minutes.setSuffix(" min")
        self.goal_effective_date = QDateEdit(QDate.currentDate())
        self.goal_effective_date.setCalendarPopup(True)
        self.goal_effective_date.setMinimumDate(QDate.currentDate())
        self.save_goal_button = QPushButton("Save goal")
        goal_form.addRow("Focus per day", self.goal_minutes)
        goal_form.addRow("Effective from", self.goal_effective_date)
        goal_form.addRow("", self.save_goal_button)
        layout.addWidget(goal_group)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        labels = (
            "Today vs goal",
            "Yesterday",
            "This week vs last",
            "Today's longest block",
            "Personal record",
            "Goal streak",
        )
        self.metric_cards = [MetricCard(label, "—", "No data yet") for label in labels]
        for index, card in enumerate(self.metric_cards):
            grid.addWidget(card, index // 3, index % 3)
        layout.addLayout(grid)
        self.motivation = QLabel()
        self.motivation.setWordWrap(True)
        self.motivation.setProperty("card", True)
        self.motivation.setAccessibleName("Today's focus challenge")
        layout.addWidget(self.motivation)
        self.empty_state = EmptyState(
            "No focus history yet",
            "Start a session when you are ready. This dashboard never fabricates progress.",
        )
        layout.addWidget(self.empty_state, 1)
        self.save_goal_button.clicked.connect(self._save_goal)
        if goals is not None:
            goals.subscribe(self.refresh)
        else:
            goal_group.setEnabled(False)
        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        if self._dashboard is None:
            self.empty_state.show()
            self.motivation.setText(
                "Begin with one focused minute; a small start is still a start."
            )
            return
        snapshot = self._dashboard.snapshot()
        self._render(snapshot)

    def _render(self, value: DashboardSnapshot) -> None:
        ratio = value.today_progress_ratio
        if value.today_goal_seconds is None:
            today_support = "No goal is effective today"
        elif ratio is None:
            today_support = "Today's stored goal is zero; choose a positive goal"
        else:
            today_support = f"{ratio * 100:.0f}% of {format_focus_time(value.today_goal_seconds)}"
        contents = (
            (format_focus_time(value.today_focus_seconds), today_support),
            (format_focus_time(value.yesterday_focus_seconds), "Allocated by local segment date"),
            (
                format_focus_time(value.current_week_seconds),
                "Last week at this point: "
                f"{format_focus_time(value.prior_week_same_point_seconds)}",
            ),
            (
                format_focus_time(value.today_longest_block_seconds),
                "Longest continuity group today",
            ),
            (
                format_focus_time(value.personal_longest_block_seconds),
                "All-time local focus record",
            ),
            (f"{value.goal_streak_days} days", "Today counts only after goal completion"),
        )
        for card, (metric, support) in zip(self.metric_cards, contents, strict=True):
            card.value.setText(metric)
            card.supporting_text.setText(support)
        self.motivation.setText(value.motivation_message)
        self.empty_state.setVisible(not value.has_focus_history)
        if self._goals is not None:
            goal = self._goals.effective_on(value.local_date)
            if goal is not None:
                self.goal_minutes.setValue(max(1, goal.goal_seconds // 60))

    def _save_goal(self) -> None:
        if self._goals is None:
            return
        chosen = self.goal_effective_date.date()
        selected = date(chosen.year(), chosen.month(), chosen.day())
        self._goals.set_goal(self.goal_minutes.value() * 60, selected)
        if self._dashboard is not None:
            self._dashboard.invalidate()
        self.refresh()
