import pytest
from PySide6.QtWidgets import QApplication

from app.models.errors import InvalidFocusSessionDraftError
from app.ui.widgets.duration_input import DurationInput


def test_duration_defaults_to_fifty_minutes_and_has_accessible_fields(
    qapp: QApplication, qtbot: object
) -> None:
    widget = DurationInput()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    assert (widget.hours, widget.minutes) == (0, 50)
    assert widget.duration_seconds() == 3000
    assert widget.hours_input.accessibleName() == "Focus duration hours"
    assert widget.minutes_input.accessibleName() == "Focus duration minutes"
    assert "50 minutes" in widget.summary_label.text()


def test_zero_is_invalid_and_one_minute_is_valid(qapp: QApplication, qtbot: object) -> None:
    widget = DurationInput()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    widget.set_duration(0, 0)
    assert not widget.is_valid
    with pytest.raises(InvalidFocusSessionDraftError):
        widget.duration_seconds()
    widget.set_duration(0, 1)
    assert widget.is_valid
    assert widget.duration_seconds() == 60


def test_duration_ui_limits_are_integer_and_below_seven_days(
    qapp: QApplication, qtbot: object
) -> None:
    widget = DurationInput(167, 59)
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    assert widget.hours_input.maximum() == 167
    assert widget.minutes_input.maximum() == 59
    assert widget.duration_seconds() == (167 * 60 + 59) * 60
