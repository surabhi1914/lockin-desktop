from dataclasses import FrozenInstanceError

import pytest

from app.models.errors import InvalidFocusSessionDraftError
from app.models.focus_session_draft import FocusSessionDraft


def _draft(**changes: object) -> FocusSessionDraft:
    values: dict[str, object] = {
        "planned_duration_seconds": 3000,
        "category_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "category_name_snapshot": "Machine Learning",
        "temporary_intention": "  Train the model  ",
        "start_in_fullscreen": True,
        "show_quotes": True,
        "play_completion_sound": True,
        "overtime_enabled": True,
        "start_ritual_enabled": True,
        "pause_grace_seconds": 10,
    }
    values.update(changes)
    return FocusSessionDraft(**values)  # type: ignore[arg-type]


def test_valid_draft_is_immutable_and_trims_intention() -> None:
    draft = _draft()
    assert draft.temporary_intention == "Train the model"
    assert draft.category_name_snapshot == "Machine Learning"
    assert not hasattr(draft, "task")
    with pytest.raises(FrozenInstanceError):
        draft.temporary_intention = "changed"  # type: ignore[misc]


def test_empty_intention_becomes_none() -> None:
    assert _draft(temporary_intention="  ").temporary_intention is None


@pytest.mark.parametrize("seconds", [0, -1, True, 604_801])
def test_invalid_duration_is_rejected(seconds: object) -> None:
    with pytest.raises(InvalidFocusSessionDraftError):
        _draft(planned_duration_seconds=seconds)


def test_invalid_category_snapshot_and_id_are_rejected() -> None:
    with pytest.raises(InvalidFocusSessionDraftError):
        _draft(category_id="bad")
    with pytest.raises(InvalidFocusSessionDraftError):
        _draft(category_name_snapshot=" ")


@pytest.mark.parametrize("intention", ["x" * 241, "bad\nvalue", "bad\tvalue"])
def test_invalid_intention_is_rejected(intention: str) -> None:
    with pytest.raises(InvalidFocusSessionDraftError):
        _draft(temporary_intention=intention)


def test_option_values_must_be_real_bools() -> None:
    with pytest.raises(InvalidFocusSessionDraftError):
        _draft(show_quotes=1)
