"""Parented, validated dialog for one finalized historical focus session."""

from dataclasses import replace
from datetime import date, datetime, time

from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtGui import QKeyEvent, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import DEFAULT_TIMEZONE
from app.diagnostics import trace_manual_session
from app.models.category import Category
from app.models.manual_session import (
    CreateManualSessionCommand,
    ManualSessionCreationResult,
)
from app.models.manual_session_errors import (
    ManualSessionError,
    ManualSessionOverlapError,
)
from app.services.manual_session_service import ManualSessionService


class AddPastSessionDialog(QDialog):
    def __init__(
        self,
        service: ManualSessionService,
        parent: QWidget,
        *,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._timezone_name = timezone_name
        self.result_record: ManualSessionCreationResult | None = None
        self.setWindowTitle("Add Past Focus Session")
        self.setModal(True)
        self.resize(560, 620)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.session_date = QDateEdit(QDate.currentDate().addDays(-1))
        self.session_date.setCalendarPopup(True)
        self.session_date.setMaximumDate(QDate.currentDate())
        self.session_date.setAccessibleName("Past session date")
        self.start_time = QTimeEdit(QTime(19, 0))
        self.start_time.setAccessibleName("Past session start time")
        self.actual_hours, self.actual_minutes, actual_row = self._duration_row(
            "Actual focus duration"
        )
        self.actual_minutes.setValue(30)
        self.category = QComboBox()
        self.category.setAccessibleName("Past session category")
        self._load_categories(service.categories())
        self.different_planned = QCheckBox("Use a different planned duration")
        self.planned_hours, self.planned_minutes, planned_row = self._duration_row(
            "Planned focus duration"
        )
        self.planned_minutes.setValue(30)
        self.planned_group = QGroupBox()
        planned_layout = QVBoxLayout(self.planned_group)
        planned_layout.setContentsMargins(0, 0, 0, 0)
        planned_layout.addWidget(planned_row)
        self.dst_occurrence = QComboBox()
        self.dst_occurrence.setAccessibleName("Daylight saving time occurrence")
        self.dst_occurrence.addItem("Automatic", None)
        self.dst_occurrence.addItem("First occurrence", 0)
        self.dst_occurrence.addItem("Second occurrence", 1)
        form.addRow("Date", self.session_date)
        form.addRow("Start time", self.start_time)
        form.addRow("Actual focus", actual_row)
        form.addRow("Category", self.category)
        form.addRow("", self.different_planned)
        form.addRow("Planned duration", self.planned_group)
        form.addRow("DST occurrence", self.dst_occurrence)
        layout.addLayout(form)
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setAccessibleName("Past session preview")
        preview_layout.addWidget(self.preview)
        layout.addWidget(preview_group)
        self.validation = QLabel()
        self.validation.setWordWrap(True)
        self.validation.setProperty("error", True)
        self.validation.setAccessibleName("Past session validation message")
        layout.addWidget(self.validation)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText("Save Past Session")
        self.save_button.setAutoDefault(False)
        self.save_button.setDefault(False)
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.different_planned.toggled.connect(self._different_planned_changed)
        self.session_date.dateChanged.connect(self._refresh_preview)
        self.start_time.timeChanged.connect(self._refresh_preview)
        for spinbox in (
            self.actual_hours,
            self.actual_minutes,
            self.planned_hours,
            self.planned_minutes,
        ):
            spinbox.valueChanged.connect(self._refresh_preview)
        self.category.currentIndexChanged.connect(self._refresh_preview)
        self.dst_occurrence.currentIndexChanged.connect(self._refresh_preview)
        self._different_planned_changed(False)
        self._refresh_preview()

    @staticmethod
    def _duration_row(accessible_name: str) -> tuple[QSpinBox, QSpinBox, QWidget]:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        hours = QSpinBox()
        hours.setRange(0, 24)
        hours.setSuffix(" h")
        hours.setAccessibleName(f"{accessible_name} hours")
        minutes = QSpinBox()
        minutes.setRange(0, 59)
        minutes.setSuffix(" min")
        minutes.setAccessibleName(f"{accessible_name} minutes")
        layout.addWidget(hours)
        layout.addWidget(minutes)
        return hours, minutes, row

    def _load_categories(self, categories: tuple[Category, ...]) -> None:
        active = tuple(item for item in categories if item.is_active)
        archived = tuple(item for item in categories if not item.is_active)
        model = self.category.model()
        assert isinstance(model, QStandardItemModel)
        for heading, values in (
            ("Active categories", active),
            ("Archived categories — historical", archived),
        ):
            self.category.addItem(heading, None)
            heading_item = model.item(self.category.count() - 1)
            heading_item.setEnabled(False)
            for category in values:
                label = (
                    category.category_name
                    if category.is_active
                    else f"{category.category_name} (Archived)"
                )
                self.category.addItem(label, category.category_id)
        first = next(
            (
                index
                for index in range(self.category.count())
                if self.category.itemData(index) is not None
            ),
            -1,
        )
        self.category.setCurrentIndex(first)

    def _different_planned_changed(self, enabled: bool) -> None:
        self.planned_group.setEnabled(enabled)
        if not enabled:
            self.planned_hours.setValue(self.actual_hours.value())
            self.planned_minutes.setValue(self.actual_minutes.value())
        self._refresh_preview()

    def _minutes(self, hours: QSpinBox, minutes: QSpinBox) -> int:
        return hours.value() * 60 + minutes.value()

    def _command(self, *, confirmed: bool = False) -> CreateManualSessionCommand:
        selected_date = self.session_date.date()
        selected_time = self.start_time.time()
        actual = self._minutes(self.actual_hours, self.actual_minutes)
        planned = (
            self._minutes(self.planned_hours, self.planned_minutes)
            if self.different_planned.isChecked()
            else actual
        )
        return CreateManualSessionCommand(
            date(selected_date.year(), selected_date.month(), selected_date.day()),
            time(selected_time.hour(), selected_time.minute()),
            actual,
            planned,
            str(self.category.currentData() or ""),
            self._timezone_name,
            self.dst_occurrence.currentData(),
            confirmed,
        )

    def _refresh_preview(self, *_args: object) -> None:
        if not self.different_planned.isChecked():
            self.planned_hours.blockSignals(True)
            self.planned_minutes.blockSignals(True)
            self.planned_hours.setValue(self.actual_hours.value())
            self.planned_minutes.setValue(self.actual_minutes.value())
            self.planned_hours.blockSignals(False)
            self.planned_minutes.blockSignals(False)
        try:
            resolved = self._service.resolve(self._command())
            category = next(
                item
                for item in self._service.categories()
                if item.category_id == resolved.command.category_id
            )
        except (ManualSessionError, StopIteration) as exc:
            self.validation.setText(str(exc))
            self.preview.clear()
            self.save_button.setEnabled(False)
            return
        self.validation.clear()
        self.save_button.setEnabled(True)
        result_labels = {
            "completed": "Manually added — completed",
            "completed_with_overtime": "Manually added — completed with overtime",
            "stopped_early": "Manually added — stopped early",
        }
        self.preview.setText(
            "\n".join(
                (
                    f"Date: {resolved.started_at.strftime('%B %d, %Y').replace(' 0', ' ')}",
                    f"Start: {self._clock_label(resolved.started_at)}",
                    f"End: {self._clock_label(resolved.ended_at)}",
                    f"Category: {category.category_name}",
                    f"Actual focus: {self._duration_label(resolved.actual_seconds)}",
                    f"Planned: {self._duration_label(resolved.planned_seconds)}",
                    f"Result: {result_labels[resolved.result.value]}",
                )
            )
        )

    def _save(self) -> None:
        command = self._command()
        try:
            self.result_record = self._service.create_manual_session(command, synchronize=False)
        except ManualSessionOverlapError as exc:
            if not exc.overlap.requires_confirmation:
                self.validation.setText(f"{exc}\n\n{self._overlap_details(exc.overlap)}")
                return
            details = self._overlap_details(exc.overlap)
            answer = QMessageBox.warning(
                self,
                "Overlapping session",
                f"{exc}\n\n{details}\n\nSave this past session anyway?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            trace_manual_session(
                "overlap-confirmation",
                confirmation="save" if answer is QMessageBox.StandardButton.Save else "cancel",
                conflict_ids=list(exc.overlap.session_ids),
            )
            if answer is not QMessageBox.StandardButton.Save:
                return
            try:
                confirmed = replace(command, overlap_confirmed=True)
                self.result_record = self._service.create_manual_session(
                    confirmed, synchronize=False
                )
            except ManualSessionError as retry_error:
                self.validation.setText(str(retry_error))
                return
        except ManualSessionError as exc:
            self.validation.setText(str(exc))
            return
        self.accept()

    @classmethod
    def _overlap_details(cls, overlap: object) -> str:
        conflicts = getattr(overlap, "conflicts", ())
        if not conflicts:
            identifiers = getattr(overlap, "session_ids", ())
            return "\n".join(f"Session: {str(identifier)[:8]}" for identifier in identifiers)
        labels = {
            "timer": "Timer recorded",
            "manual": "Manual",
            "recovery": "Recovery",
            "imported": "Imported",
        }
        sections: list[str] = []
        for conflict in conflicts:
            started = datetime.fromisoformat(conflict.started_at_local)
            ended = datetime.fromisoformat(conflict.ended_at_local)
            end_label = cls._clock_label(ended)
            if ended.date() != started.date():
                end_label = f"{ended.strftime('%B %d, %Y').replace(' 0', ' ')} {end_label}"
            sections.append(
                "\n".join(
                    (
                        "This time overlaps another session:",
                        started.strftime("%B %d, %Y").replace(" 0", " "),
                        f"{cls._clock_label(started)}\N{EN DASH}{end_label}",
                        conflict.category_name,
                        labels.get(conflict.entry_source, conflict.entry_source.title()),
                        f"Status: {conflict.status}",
                        f"Session: {conflict.session_id[:8]}",
                    )
                )
            )
        return "\n\n".join(sections)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()
            return
        super().keyPressEvent(event)

    @staticmethod
    def _clock_label(value: datetime) -> str:
        return value.strftime("%I:%M %p").lstrip("0")

    @staticmethod
    def _duration_label(seconds: int) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60
        if hours and minutes:
            return f"{hours}h {minutes}m"
        if hours:
            return f"{hours}h"
        return f"{minutes}m"
