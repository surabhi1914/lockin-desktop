"""Complete read-only statistics filters, metrics, native charts, and export."""

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.analytics.analytics_service import AnalyticsService
from app.analytics.date_presets import DatePreset, preset_range
from app.analytics.export_service import StatisticsExportService
from app.analytics.history_service import HistoryService
from app.analytics.models import AnalyticsFilters, StatisticsResult
from app.ui.charts import CalendarHeatmap, ChartKind, MetricChart
from app.ui.focus.focus_canvas import format_focus_time
from app.ui.widgets import MetricCard, PageHeader


class StatisticsPage(QWidget):
    def __init__(
        self,
        analytics: AnalyticsService | None = None,
        history: HistoryService | None = None,
        exporter: StatisticsExportService | None = None,
    ) -> None:
        super().__init__()
        self._analytics = analytics
        self._history = history
        self._exporter = exporter
        self.last_result: StatisticsResult | None = None
        self.setObjectName("page_statistics")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.addWidget(PageHeader("Statistics", "Local, read-only focus analytics."))
        controls = QGroupBox("Range and filters")
        form = QFormLayout(controls)
        self.preset = QComboBox()
        for preset in DatePreset:
            if preset is not DatePreset.CUSTOM:
                self.preset.addItem(preset.value.replace("_", " ").title(), preset.value)
        self.from_date = QDateEdit()
        self.to_date = QDateEdit()
        for editor in (self.from_date, self.to_date):
            editor.setCalendarPopup(True)
        self.category = QComboBox()
        self.status = QComboBox()
        self.device = QComboBox()
        self.source = QComboBox()
        self.include_overtime = QCheckBox("Include overtime")
        self.include_overtime.setChecked(True)
        self.include_recovered = QCheckBox("Include recovered")
        self.include_recovered.setChecked(True)
        self.minimum_minutes = QSpinBox()
        self.minimum_minutes.setRange(0, 10_080)
        self.minimum_minutes.setSuffix(" min")
        form.addRow("Preset", self.preset)
        form.addRow("From", self.from_date)
        form.addRow("To", self.to_date)
        form.addRow("Category", self.category)
        form.addRow("Status", self.status)
        form.addRow("Device", self.device)
        form.addRow("Source", self.source)
        form.addRow("", self.include_overtime)
        form.addRow("", self.include_recovered)
        form.addRow("Minimum focus", self.minimum_minutes)
        includes_manual = QLabel("Totals include manually added sessions unless filtered out.")
        includes_manual.setProperty("muted", True)
        form.addRow("", includes_manual)
        buttons = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.export_button = QPushButton("Export Statistics CSV")
        self.heatmap_goal_mode = QCheckBox("Heatmap relative to goal")
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.export_button)
        buttons.addWidget(self.heatmap_goal_mode)
        buttons.addStretch(1)
        form.addRow("", buttons)
        outer.addWidget(controls)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        metrics = QGridLayout()
        self.metric_cards = [
            MetricCard("Total focus", "00:00", "Selected local-date range"),
            MetricCard("Active days", "0", "Days with confirmed focus"),
            MetricCard("Sessions", "0", "Discarded excluded"),
            MetricCard("Completion rate", "—", "Session-start semantics"),
            MetricCard("Longest block", "00:00", "Continuity groups"),
            MetricCard("Distractions/hour", "—", "Simple markers per focus hour"),
        ]
        for index, card in enumerate(self.metric_cards):
            metrics.addWidget(card, index // 3, index % 3)
        layout.addLayout(metrics)
        self.metric_dictionary = QLabel()
        self.metric_dictionary.setWordWrap(True)
        self.metric_dictionary.setTextInteractionFlags(
            self.metric_dictionary.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.metric_dictionary)
        charts = QGridLayout()
        self.charts = [
            MetricChart("Daily focus", ChartKind.DAILY),
            MetricChart("Weekly comparison", ChartKind.WEEKLY),
            MetricChart("Category breakdown", ChartKind.CATEGORY),
            MetricChart("Planned vs actual", ChartKind.PLANNED_ACTUAL),
            MetricChart("Pause / distraction trend", ChartKind.PAUSE_DISTRACTION),
            MetricChart("Continuous block distribution", ChartKind.BLOCKS),
        ]
        for index, chart in enumerate(self.charts):
            charts.addWidget(chart, index // 2, index % 2)
        layout.addLayout(charts)
        self.heatmap = CalendarHeatmap()
        layout.addWidget(self.heatmap)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self.preset.currentIndexChanged.connect(self._preset_changed)
        self.apply_button.clicked.connect(self.refresh)
        self.export_button.clicked.connect(self._export)
        self.heatmap_goal_mode.toggled.connect(self.heatmap.set_goal_mode)
        self._load_options()
        self._preset_changed()
        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        if self._analytics is None:
            self.metric_dictionary.setText("No local analytics service is available.")
            return
        start = self.from_date.date()
        end = self.to_date.date()
        filters = AnalyticsFilters(
            date(start.year(), start.month(), start.day()).isoformat(),
            date(end.year(), end.month(), end.day()).isoformat(),
            self._selected(self.category),
            self._selected(self.status),
            self._selected(self.device),
            self.include_overtime.isChecked(),
            self.include_recovered.isChecked(),
            self.minimum_minutes.value() * 60,
            entry_sources=self._selected(self.source),
        )
        try:
            result = self._analytics.calculate(filters)
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Statistics unavailable", str(exc))
            return
        self.last_result = result
        self._render(result)

    def _render(self, value: StatisticsResult) -> None:
        card_values = (
            format_focus_time(value.total_focus_seconds),
            str(value.active_days),
            str(value.session_count),
            self._percent(value.completion_rate),
            format_focus_time(value.longest_block_seconds),
            "—"
            if value.distractions_per_focus_hour is None
            else f"{value.distractions_per_focus_hour:.2f}",
        )
        for card, text in zip(self.metric_cards, card_values, strict=True):
            card.value.setText(text)
        self.metric_dictionary.setText(
            " · ".join(
                (
                    f"Average/median active day {value.average_focus_per_active_day_seconds}s/"
                    f"{value.median_focus_per_active_day_seconds}s",
                    f"Goal-met days {value.goal_met_days}",
                    f"Planned/completed/stopped/overtime {value.planned_seconds}s/"
                    f"{value.planned_completed_seconds}s/{value.stopped_early_seconds}s/"
                    f"{value.overtime_seconds}s",
                    f"Blocks count/avg/median {value.block_count}/{value.average_block_seconds}s/"
                    f"{value.median_block_seconds}s",
                    f"Pauses total/count/short/long/sleep {value.total_pause_seconds}s/"
                    f"{value.pause_count}/{value.short_pause_count}/{value.long_pause_count}/"
                    f"{value.system_sleep_pause_count}",
                    f"Distractions total/marked sessions {value.distraction_count}/"
                    f"{value.sessions_with_distractions}",
                )
            )
        )
        for chart in self.charts:
            chart.set_result(value)
        self.heatmap.set_result(value)

    def _load_options(self) -> None:
        for combo, label in (
            (self.category, "All categories"),
            (self.status, "All statuses"),
            (self.device, "All devices"),
            (self.source, "All sources"),
        ):
            combo.addItem(label, "")
        if self._history is None:
            return
        options = self._history.filter_options()
        for identifier, label in options["categories"]:
            self.category.addItem(label, identifier)
        for identifier, label in options["statuses"]:
            self.status.addItem(label, identifier)
        for identifier, label in options["devices"]:
            self.device.addItem(label, identifier)
        for identifier, label in options["sources"]:
            self.source.addItem(label, identifier)

    def _preset_changed(self) -> None:
        preset = DatePreset(str(self.preset.currentData()))
        start, end = preset_range(preset, date.today())
        self.from_date.setDate(QDate(start.year, start.month, start.day))
        self.to_date.setDate(QDate(end.year, end.month, end.day))

    def _export(self) -> None:
        if self._exporter is None or self.last_result is None:
            return
        selected, _kind = QFileDialog.getSaveFileName(
            self, "Export statistics", "lockin_statistics.csv", "CSV (*.csv)"
        )
        if not selected:
            return
        try:
            path = self._exporter.export(self.last_result, Path(selected))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Statistics exported", f"Saved {path}")

    @staticmethod
    def _selected(combo: QComboBox) -> tuple[str, ...]:
        value = str(combo.currentData() or "")
        return () if not value else (value,)

    @staticmethod
    def _percent(value: float | None) -> str:
        return "—" if value is None else f"{value * 100:.1f}%"
