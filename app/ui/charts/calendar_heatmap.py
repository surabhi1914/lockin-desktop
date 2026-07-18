"""Calendar-aligned local-date heatmap with absolute/goal modes."""

from datetime import date

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from app.analytics.models import DailyMetric, StatisticsResult


class CalendarHeatmap(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: tuple[DailyMetric, ...] = ()
        self._goal_mode = False
        self._cells: list[tuple[QRectF, DailyMetric]] = []
        self.setMinimumHeight(210)
        self.setMouseTracking(True)
        self.setAccessibleName("Calendar focus heatmap")

    def set_result(self, result: StatisticsResult) -> None:
        self._rows = result.daily
        self.update()

    def set_goal_mode(self, enabled: bool) -> None:
        self._goal_mode = enabled
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.palette().base())
        painter.setPen(self.palette().text().color())
        painter.drawText(12, 24, "Calendar heatmap · local dates")
        if not self._rows:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No dates in this range")
            return
        first = date.fromisoformat(self._rows[0].local_date)
        maximum = max((row.focus_seconds for row in self._rows), default=1) or 1
        size = min(18.0, max(8.0, (self.width() - 52) / max(1, len(self._rows) / 7 + 1)))
        self._cells.clear()
        for row in self._rows:
            day = date.fromisoformat(row.local_date)
            if day > date.today():
                continue
            absolute = (day - first).days + first.weekday()
            week, weekday = divmod(absolute, 7)
            rect = QRectF(42 + week * (size + 3), 38 + weekday * (size + 3), size, size)
            ratio = (
                row.focus_seconds / row.goal_seconds
                if self._goal_mode and row.goal_seconds > 0
                else row.focus_seconds / maximum
            )
            ratio = max(0.0, min(1.0, ratio))
            color = QColor(self.palette().highlight().color())
            color.setAlphaF(0.12 + ratio * 0.88)
            painter.fillRect(rect, color)
            if day == date.today():
                painter.setPen(QPen(self.palette().text().color(), 2))
                painter.drawRect(rect)
            self._cells.append((rect, row))
        painter.setPen(self.palette().text().color())
        painter.drawText(8, 54, "Mon")
        painter.drawText(8, int(54 + 6 * (size + 3)), "Sun")

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        row = next((item for rect, item in self._cells if rect.contains(event.position())), None)
        if row is not None:
            self.setToolTip(
                f"{row.local_date}: focus {row.focus_seconds}s, goal {row.goal_seconds}s, "
                f"sessions {row.session_count}, longest {row.longest_block_seconds}s"
            )
        super().mouseMoveEvent(event)
