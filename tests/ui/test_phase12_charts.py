from PySide6.QtWidgets import QApplication

from app.analytics.analytics_service import AnalyticsService
from app.analytics.models import AnalyticsFilters
from app.themes.theme_service import ThemeService
from app.ui.charts import CalendarHeatmap, ChartKind, MetricChart
from tests.integration.test_phase12_analytics import _fixture


def test_all_native_charts_render_across_themes(qapp: QApplication, qtbot, tmp_path) -> None:
    connection, _devices, _categories = _fixture(tmp_path)
    result = AnalyticsService(connection).calculate(AnalyticsFilters("2026-07-16", "2026-07-17"))
    charts = [MetricChart(kind.value, kind) for kind in ChartKind]
    heatmap = CalendarHeatmap()
    for widget in (*charts, heatmap):
        qtbot.addWidget(widget)
        widget.resize(520, 260)
        widget.show()
    service = ThemeService(qapp)
    for theme in service.registry.themes:
        service.apply(theme.theme_id)
        for chart in charts:
            chart.set_result(result)
            assert not chart.grab().isNull()
            assert chart.accessibleDescription()
        heatmap.set_result(result)
        heatmap.set_goal_mode(True)
        assert not heatmap.grab().isNull()
        assert len(heatmap._cells) == 2
