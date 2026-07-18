from PySide6.QtWidgets import QApplication

from app.ui.focus.start_ritual import RitualDurations, StartRitual


def test_ritual_runs_breath_intention_countdown_and_completes_without_blocking(
    qapp: QApplication, qtbot: object
) -> None:
    ritual = StartRitual(
        durations=RitualDurations(1, 1, 1, 0),
        reduced_motion=True,
    )
    qtbot.addWidget(ritual)  # type: ignore[attr-defined]
    completions: list[str] = []
    ritual.completed.connect(lambda: completions.append("done"))
    ritual.start("Write the draft")
    assert ritual.active
    assert ritual.prompt_label.text() == "Take one slow breath."
    assert ritual.intention_label.text() == "Write the draft"
    qtbot.waitUntil(lambda: completions == ["done"], timeout=1000)  # type: ignore[attr-defined]
    assert not ritual.active


def test_ritual_cancel_is_once_only_and_shutdown_clears_intention(
    qapp: QApplication, qtbot: object
) -> None:
    ritual = StartRitual(durations=RitualDurations(100, 100, 100, 100))
    qtbot.addWidget(ritual)  # type: ignore[attr-defined]
    cancelled: list[str] = []
    ritual.cancelled.connect(lambda: cancelled.append("cancelled"))
    ritual.start("Temporary")
    ritual.cancel()
    ritual.cancel()
    ritual.shutdown()
    assert cancelled == ["cancelled"]
    assert ritual.intention_label.text() == ""


def test_ritual_stage_order_is_breath_intention_three_two_one(
    qapp: QApplication, qtbot: object
) -> None:
    ritual = StartRitual(durations=RitualDurations(100, 100, 100, 0), reduced_motion=True)
    qtbot.addWidget(ritual)  # type: ignore[attr-defined]
    ritual.start("One task")
    assert ritual.prompt_label.isVisibleTo(ritual)
    ritual._timer.stop()
    ritual._advance()
    assert ritual.intention_label.isVisibleTo(ritual)
    for expected in ("3", "2", "1"):
        ritual._timer.stop()
        ritual._advance()
        assert ritual.countdown_label.text() == expected
    ritual.cancel()
