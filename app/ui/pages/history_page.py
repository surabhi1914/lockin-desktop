"""Advanced read-only, paginated Session History and detail inspection."""

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.analytics.history_service import HistoryFilters, HistoryService, SessionDetail
from app.services.session_aggregate_service import SessionAggregateService
from app.ui.widgets import EmptyState, PageHeader


class SessionDetailDialog(QDialog):
    def __init__(self, detail: SessionDetail, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.detail = detail
        self.setWindowTitle("Session details")
        self.resize(760, 620)
        layout = QVBoxLayout(self)
        text = QTextEdit()
        text.setReadOnly(True)
        session = detail.session
        lines = [
            f"Session ID: {session.session_id}",
            f"Category: {session.category_name_snapshot}",
            f"Status/reason: {session.status} / {session.completion_reason or '—'}",
            f"Started/ended: {session.started_at_local} / {session.ended_at_local}",
            f"Planned/planned completed/overtime: {session.planned_focus_seconds}s / "
            f"{session.planned_focus_completed_seconds}s / {session.overtime_seconds}s",
            f"Actual/pause: {session.actual_focus_seconds}s / {session.total_pause_seconds}s",
            f"Continuity blocks: {session.continuous_block_count}; longest "
            f"{session.longest_continuous_seconds}s; median {session.median_continuous_seconds}s",
            f"Pauses short/long: {session.short_pause_count}/{session.long_pause_count}",
            f"Distractions: {session.distraction_count}",
            f"Checksum: {session.record_checksum or 'pending'}",
            "",
            "Segments:",
        ]
        lines.extend(
            f"  #{item.segment_sequence} {item.segment_type}/{item.focus_phase} "
            f"{item.duration_seconds}s {item.pause_classification} group="
            f"{item.continuity_group_id or '—'}"
            for item in detail.segments
        )
        lines.append("Distractions:")
        lines.extend(
            f"  {item.marked_at_local} elapsed={item.elapsed_focus_seconds}s"
            for item in detail.distractions
        )
        lines.append("Recovery audit:")
        lines.extend(
            f"  {item.event_type} unknown={item.unknown_gap_seconds}s "
            f"action={item.selected_action or 'pending'}"
            for item in detail.recovery_events
        )
        lines.append("Portable sync:")
        lines.extend(
            f"  {item.record_type}: {item.partition_relative_path} {item.record_checksum}"
            for item in detail.sync_entries
        )
        text.setPlainText("\n".join(lines))
        layout.addWidget(text)
        copy = QPushButton("Copy full session ID")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(session.session_id))
        layout.addWidget(copy)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)


class HistoryPage(QWidget):
    def __init__(
        self,
        aggregate_service: SessionAggregateService | None = None,
        history_service: HistoryService | None = None,
    ) -> None:
        super().__init__()
        self._aggregates = aggregate_service
        self._history = history_service
        self._page = 1
        self._session_ids: list[str] = []
        self.setObjectName("page_history")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(PageHeader("Session History", "Read-only finalized session records."))
        filters = QGridLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search category or full session ID")
        self.category = QComboBox()
        self.status = QComboBox()
        self.device = QComboBox()
        self.sort = QComboBox()
        for label, value in (
            ("Newest", "started_desc"),
            ("Oldest", "started_asc"),
            ("Most focus", "focus_desc"),
            ("Least focus", "focus_asc"),
            ("Category", "category"),
        ):
            self.sort.addItem(label, value)
        self.overtime_only = QCheckBox("Overtime only")
        self.distraction_only = QCheckBox("With distractions")
        self.minimum_minutes = QSpinBox()
        self.minimum_minutes.setRange(0, 10_080)
        self.minimum_minutes.setSuffix(" min minimum")
        self.maximum_minutes = QSpinBox()
        self.maximum_minutes.setRange(0, 10_080)
        self.maximum_minutes.setSpecialValueText("No maximum")
        self.maximum_minutes.setSuffix(" min maximum")
        self.from_date = QDateEdit(QDate(2000, 1, 1))
        self.to_date = QDateEdit(QDate.currentDate())
        self.from_date.setCalendarPopup(True)
        self.to_date.setCalendarPopup(True)
        filters.addWidget(self.search, 0, 0, 1, 2)
        filters.addWidget(self.category, 0, 2)
        filters.addWidget(self.status, 0, 3)
        filters.addWidget(self.device, 0, 4)
        filters.addWidget(self.sort, 1, 0)
        filters.addWidget(self.minimum_minutes, 1, 1)
        filters.addWidget(self.maximum_minutes, 1, 2)
        filters.addWidget(self.overtime_only, 1, 3)
        filters.addWidget(self.distraction_only, 1, 4)
        filters.addWidget(QLabel("From"), 2, 0)
        filters.addWidget(self.from_date, 2, 1)
        filters.addWidget(QLabel("To"), 2, 2)
        filters.addWidget(self.to_date, 2, 3)
        layout.addLayout(filters)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            (
                "Date",
                "Category",
                "Device",
                "Planned",
                "Focus",
                "Overtime",
                "Pause",
                "Distractions",
                "Status",
            )
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.empty = EmptyState(
            "No matching sessions", "Adjust filters or complete a focus session."
        )
        layout.addWidget(self.table, 1)
        layout.addWidget(self.empty, 1)
        paging = QHBoxLayout()
        self.previous_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.page_label = QLabel()
        self.details_button = QPushButton("View details")
        paging.addWidget(self.previous_button)
        paging.addWidget(self.next_button)
        paging.addWidget(self.page_label)
        paging.addStretch(1)
        paging.addWidget(self.details_button)
        layout.addLayout(paging)
        self._load_options()
        for control in (
            self.search,
            self.category,
            self.status,
            self.device,
            self.sort,
            self.minimum_minutes,
            self.maximum_minutes,
            self.overtime_only,
            self.distraction_only,
            self.from_date,
            self.to_date,
        ):
            signal = (
                getattr(control, "textChanged", None)
                or getattr(control, "currentIndexChanged", None)
                or getattr(control, "valueChanged", None)
                or getattr(control, "dateChanged", None)
                or getattr(control, "toggled", None)
            )
            if signal is not None:
                signal.connect(self._filters_changed)
        self.previous_button.clicked.connect(self._previous)
        self.next_button.clicked.connect(self._next)
        self.details_button.clicked.connect(self._details)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._details())
        self.refresh()

    def refresh(self) -> None:
        if self._history is None:
            rows = self._aggregates.latest(20) if self._aggregates is not None else ()
            self._session_ids = [row.session_id for row in rows]
            values = [
                (
                    row.started_at_local,
                    row.category_name,
                    "Local device",
                    row.planned_duration_seconds,
                    row.total_focus_seconds,
                    row.overtime_seconds,
                    row.total_pause_seconds,
                    row.distraction_count,
                    row.status,
                )
                for row in rows
            ]
            total = len(values)
        else:
            result = self._history.search(self._filters())
            self._session_ids = [row.session_id for row in result.rows]
            values = [
                (
                    row.started_at_local,
                    row.category_name,
                    row.device_label,
                    row.planned_seconds,
                    row.focus_seconds,
                    row.overtime_seconds,
                    row.pause_seconds,
                    row.distraction_count,
                    row.status,
                )
                for row in result.rows
            ]
            total = result.total_count
        self.table.setRowCount(len(values))
        for row_index, row in enumerate(values):
            for column, value in enumerate(row):
                self.table.setItem(row_index, column, QTableWidgetItem(str(value)))
        self.table.setVisible(bool(values))
        self.empty.setVisible(not values)
        pages = max(1, (total + 49) // 50)
        self.page_label.setText(f"Page {self._page} of {pages} · {total} sessions")
        self.previous_button.setEnabled(self._page > 1)
        self.next_button.setEnabled(self._page < pages)

    def showEvent(self, event: QShowEvent) -> None:
        self.refresh()
        super().showEvent(event)

    def _filters(self) -> HistoryFilters:
        maximum = self.maximum_minutes.value()
        start = self.from_date.date()
        end = self.to_date.date()
        return HistoryFilters(
            search=self.search.text(),
            from_date=date(start.year(), start.month(), start.day()).isoformat(),
            to_date=date(end.year(), end.month(), end.day()).isoformat(),
            category_ids=self._selected(self.category),
            statuses=self._selected(self.status),
            device_ids=self._selected(self.device),
            overtime_only=self.overtime_only.isChecked(),
            distraction_only=self.distraction_only.isChecked(),
            minimum_focus_seconds=self.minimum_minutes.value() * 60,
            maximum_focus_seconds=None if maximum == 0 else maximum * 60,
            sort_by=str(self.sort.currentData()),
            page=self._page,
        )

    def _load_options(self) -> None:
        for combo, label in (
            (self.category, "All categories"),
            (self.status, "All statuses"),
            (self.device, "All devices"),
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

    def _filters_changed(self, *_args: object) -> None:
        self._page = 1
        self.refresh()

    def _previous(self) -> None:
        self._page = max(1, self._page - 1)
        self.refresh()

    def _next(self) -> None:
        self._page += 1
        self.refresh()

    def _details(self) -> None:
        if self._history is None:
            return
        row = self.table.currentRow()
        if not 0 <= row < len(self._session_ids):
            return
        SessionDetailDialog(self._history.detail(self._session_ids[row]), self).exec()

    @staticmethod
    def _selected(combo: QComboBox) -> tuple[str, ...]:
        value = str(combo.currentData() or "")
        return () if not value else (value,)
