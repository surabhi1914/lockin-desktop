from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.models.errors import FocusSessionAlreadyActiveError, NoActiveFocusSessionError
from app.models.focus_session_draft import FocusSessionDraft
from app.services.focus_session_coordinator import FocusSessionCoordinator
from app.timer import ManualClock, TimerState
from tests.phase3_helpers import isolated_category_service, path_config


def _draft(
    category_id: str, name: str, intention: str | None = "Ship one thing"
) -> FocusSessionDraft:
    return FocusSessionDraft(
        60,
        category_id,
        name,
        intention,
        True,
        True,
        True,
        True,
        True,
        10,
    )


def test_coordinator_handoff_controls_timer_and_clears_intention(
    qapp: QApplication, tmp_path: Path
) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    clock = ManualClock()
    coordinator = FocusSessionCoordinator(service, clock_factory=lambda: clock)
    category = service.list_active()[0]
    try:
        context = coordinator.start(_draft(category.category_id, category.category_name))
        assert context.snapshot.state is TimerState.RUNNING
        assert context.draft.temporary_intention == "Ship one thing"
        clock.advance_seconds(5)
        coordinator.adapter.poll_once()
        coordinator.pause()
        clock.advance_seconds(2)
        coordinator.adapter.poll_once()
        coordinator.resume()
        stopped = coordinator.stop_and_end()
        assert stopped.planned_focus_seconds == 5
        assert coordinator.current_context is None
        with pytest.raises(NoActiveFocusSessionError):
            _ = coordinator.engine
    finally:
        coordinator.shutdown()
        connection.close()


def test_second_start_rejected_and_reset_uses_fresh_engine(
    qapp: QApplication, tmp_path: Path
) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    clocks = [ManualClock(), ManualClock()]
    coordinator = FocusSessionCoordinator(service, clock_factory=lambda: clocks.pop(0))
    category = service.list_active()[0]
    draft = _draft(category.category_id, category.category_name)
    try:
        coordinator.start(draft)
        first = coordinator.engine
        with pytest.raises(FocusSessionAlreadyActiveError):
            coordinator.start(draft)
        coordinator.reset()
        coordinator.start(draft)
        assert coordinator.engine is not first
    finally:
        coordinator.shutdown()
        connection.close()


def test_archived_category_is_rechecked_at_start(qapp: QApplication, tmp_path: Path) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    category = next(item for item in service.list_active() if item.category_name != "Other")
    draft = _draft(category.category_id, category.category_name)
    service.archive(category.category_id)
    coordinator = FocusSessionCoordinator(service, clock_factory=ManualClock)
    try:
        with pytest.raises(Exception, match="archived"):
            coordinator.start(draft)
    finally:
        coordinator.shutdown()
        connection.close()
