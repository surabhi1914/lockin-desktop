"""Compact custom-painted charts with zero baselines and text summaries."""

from datetime import date, timedelta
from enum import StrEnum

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from app.analytics.models import StatisticsResult


class ChartKind(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    CATEGORY = "category"
    PLANNED_ACTUAL = "planned_actual"
    PAUSE_DISTRACTION = "pause_distraction"
    BLOCKS = "blocks"


class MetricChart(QWidget):
    def __init__(self, title: str, kind: ChartKind, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.kind = kind
        self._result: StatisticsResult | None = None
        self._bars: list[tuple[QRectF, str]] = []
        self.setMinimumHeight(220)
        self.setMouseTracking(True)
        self.setAccessibleName(f"{title} chart")

    def set_result(self, result: StatisticsResult) -> None:
        self._result = result
        self.setAccessibleDescription(self._summary(result))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.palette().base())
        painter.setPen(self.palette().text().color())
        title_font = painter.font()
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(QRectF(12, 8, self.width() - 24, 24), self.title)
        result = self._result
        if result is None or not self._values(result):
            painter.setFont(self.font())
            painter.setPen(self.palette().placeholderText().color())
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data in this range")
            return
        values = self._values(result)
        maximum = max(value for _label, value in values)
        if maximum <= 0:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No activity in this range")
            return
        plot = QRectF(42, 42, self.width() - 58, self.height() - 78)
        painter.setPen(QPen(self.palette().mid().color(), 1))
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())
        painter.drawText(QRectF(2, 38, 36, 18), str(maximum))
        self._bars.clear()
        gap = 4.0
        width = max(2.0, (plot.width() - gap * (len(values) - 1)) / len(values))
        accent = QColor(self.palette().highlight().color())
        for index, (label, value) in enumerate(values):
            height = plot.height() * value / maximum
            rect = QRectF(
                plot.left() + index * (width + gap), plot.bottom() - height, width, height
            )
            painter.fillRect(rect, accent)
            tooltip = f"{label}: {value} seconds"
            if self.kind is ChartKind.PAUSE_DISTRACTION and index < len(result.daily):
                tooltip += f"; {result.daily[index].distraction_count} distraction markers"
            self._bars.append((rect, tooltip))
        if self.kind is ChartKind.PAUSE_DISTRACTION:
            maximum_markers = max((row.distraction_count for row in result.daily), default=0)
            if maximum_markers:
                painter.setPen(QPen(QColor("#d08080"), 2))
                for index, row in enumerate(result.daily):
                    x = plot.left() + index * (width + gap) + width / 2
                    y = plot.bottom() - plot.height() * row.distraction_count / maximum_markers
                    painter.drawEllipse(QPointF(x, y), 3, 3)
                painter.drawText(
                    QRectF(plot.right() - 110, plot.top(), 108, 18),
                    Qt.AlignmentFlag.AlignRight,
                    f"markers max {maximum_markers}",
                )
        painter.setPen(self.palette().text().color())
        painter.drawText(
            QRectF(plot.left(), plot.bottom() + 8, plot.width(), 22),
            Qt.AlignmentFlag.AlignCenter,
            self._axis_label(values),
        )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        point = QPointF(event.position())
        match = next((text for rect, text in self._bars if rect.contains(point)), "")
        self.setToolTip(match or (self._summary(self._result) if self._result else ""))
        super().mouseMoveEvent(event)

    def _values(self, result: StatisticsResult) -> list[tuple[str, int]]:
        if self.kind is ChartKind.DAILY:
            return [(row.local_date, row.focus_seconds) for row in result.daily]
        if self.kind is ChartKind.WEEKLY:
            weeks: dict[str, int] = {}
            for row in result.daily:
                day = date.fromisoformat(row.local_date)
                key = (day - timedelta(days=day.weekday())).isoformat()
                weeks[key] = weeks.get(key, 0) + row.focus_seconds
            return list(weeks.items())
        if self.kind is ChartKind.CATEGORY:
            return [(row.category_name, row.focus_seconds) for row in result.categories]
        if self.kind is ChartKind.PLANNED_ACTUAL:
            return [("Planned", result.planned_seconds), ("Actual", result.total_focus_seconds)]
        if self.kind is ChartKind.PAUSE_DISTRACTION:
            return [(row.local_date, row.pause_seconds) for row in result.daily]
        return [(label, count) for label, count in result.block_buckets]

    @staticmethod
    def _axis_label(values: list[tuple[str, int]]) -> str:
        if len(values) == 1:
            return values[0][0]
        return f"{values[0][0]}  →  {values[-1][0]} · baseline 0"

    def _summary(self, result: StatisticsResult | None) -> str:
        if result is None:
            return "No statistics loaded"
        return (
            f"{self.title}: {result.total_focus_seconds} focus seconds across "
            f"{result.active_days} active days"
        )
