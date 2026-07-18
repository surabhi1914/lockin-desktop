from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.models.focus_session_draft import FocusSessionDraft
from app.services.focus_session_coordinator import FocusSessionCoordinator
from app.timer import ManualClock, TimerState
from tests.phase3_helpers import isolated_category_service, path_config


def test_valid_draft_hands_exact_options_to_fresh_timer(qapp: QApplication, tmp_path: Path) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    category = next(
        item for item in service.list_active() if item.category_name == "Machine Learning"
    )
    clocks = [ManualClock(), ManualClock()]
    coordinator = FocusSessionCoordinator(service, clock_factory=lambda: clocks.pop(0))
    draft = FocusSessionDraft(
        90,
        category.category_id,
        category.category_name,
        "Train one model",
        True,
        False,
        False,
        False,
        True,
        10,
    )
    try:
        context = coordinator.start(draft)
        first_engine = coordinator.engine
        assert context.snapshot.state is TimerState.RUNNING
        assert first_engine.config.planned_duration_seconds == 90
        assert not first_engine.config.overtime_enabled
        coordinator.stop_and_end()
        coordinator.start(draft)
        assert coordinator.engine is not first_engine
    finally:
        coordinator.shutdown()
        connection.close()
