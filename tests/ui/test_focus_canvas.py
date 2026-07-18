from PySide6.QtGui import QPalette, QShortcut
from PySide6.QtWidgets import QApplication

from app.services.portable_preview_service import QuotePreview
from app.timer import ManualClock, TimerConfig, TimerEngine
from app.ui.focus.focus_canvas import FocusCanvas, format_focus_time, format_overtime


def test_timer_formats_and_canvas_is_black_snapshot_driven(
    qapp: QApplication, qtbot: object
) -> None:
    assert format_focus_time(0) == "00:00"
    assert format_focus_time(3599) == "59:59"
    assert format_focus_time(3600) == "01:00:00"
    assert format_overtime(12) == "+00:00:12"
    canvas = FocusCanvas(inactivity_ms=20)
    qtbot.addWidget(canvas)  # type: ignore[attr-defined]
    canvas.resize(940, 620)
    canvas.show()
    quote = QuotePreview("q1", "Stay with the work.", "", "")
    canvas.begin("Machine Learning", quote)
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(60), clock)
    engine.start()
    clock.advance_seconds(5)
    snapshot = engine.snapshot()
    canvas.render_snapshot(snapshot)
    assert "#000000" in canvas.styleSheet()
    assert canvas.palette().color(QPalette.ColorRole.Window).name() == "#000000"
    assert canvas.timer_label.text() == "00:55"
    assert canvas.category_label.text() == "Machine Learning"
    assert canvas.quote_label.text() == "“Stay with the work.”"
    assert canvas.timer_label.font().pixelSize() >= 52
    assert canvas.findChildren(QShortcut) == []


def test_controls_and_cursor_hide_only_while_active_and_reveal_on_activity(
    qapp: QApplication, qtbot: object
) -> None:
    canvas = FocusCanvas(inactivity_ms=15)
    qtbot.addWidget(canvas)  # type: ignore[attr-defined]
    canvas.show()
    canvas.begin("Other", None)
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(60), clock)
    engine.start()
    canvas.render_snapshot(engine.snapshot())
    qtbot.waitUntil(lambda: canvas.cursor_hidden, timeout=1000)  # type: ignore[attr-defined]
    assert not canvas.controls_visible
    canvas.note_pointer_activity(near_bottom=True)
    assert canvas.controls_visible
    assert not canvas.cursor_hidden
    engine.pause()
    canvas.render_snapshot(engine.snapshot())
    qtbot.wait(30)  # type: ignore[attr-defined]
    assert canvas.controls_visible
    assert not canvas.cursor_hidden
