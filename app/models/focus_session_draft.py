"""Immutable validated in-memory focus-session setup draft."""

from dataclasses import dataclass
from unicodedata import category as unicode_category

from app.core.errors import ValidationError
from app.core.ids import canonicalize_uuid
from app.models.category import normalize_category_name
from app.models.errors import CategoryError, InvalidFocusSessionDraftError
from app.timer.errors import InvalidTimerConfigurationError
from app.timer.models import TimerConfig

MAX_INTENTION_LENGTH = 240


@dataclass(frozen=True, slots=True)
class FocusSessionDraft:
    """Setup values held only for the current application process."""

    planned_duration_seconds: int
    category_id: str
    category_name_snapshot: str
    temporary_intention: str | None
    start_in_fullscreen: bool
    show_quotes: bool
    play_completion_sound: bool
    overtime_enabled: bool
    start_ritual_enabled: bool
    pause_grace_seconds: int = 10

    def __post_init__(self) -> None:
        try:
            TimerConfig(
                planned_duration_seconds=self.planned_duration_seconds,
                pause_grace_seconds=self.pause_grace_seconds,
                overtime_enabled=self.overtime_enabled,
            )
        except InvalidTimerConfigurationError as exc:
            raise InvalidFocusSessionDraftError(str(exc)) from exc
        try:
            canonical_id = canonicalize_uuid(self.category_id)
        except ValidationError as exc:
            raise InvalidFocusSessionDraftError(str(exc)) from exc
        if canonical_id != self.category_id:
            raise InvalidFocusSessionDraftError("category_id must be a canonical lowercase UUID")
        try:
            snapshot = normalize_category_name(self.category_name_snapshot)
        except CategoryError as exc:
            raise InvalidFocusSessionDraftError(f"invalid category name snapshot: {exc}") from exc
        object.__setattr__(self, "category_name_snapshot", snapshot)
        intention = self.temporary_intention
        if intention is not None:
            if not isinstance(intention, str):
                raise InvalidFocusSessionDraftError("temporary intention must be text or None")
            intention = intention.strip()
            if not intention:
                intention = None
            elif any(unicode_category(character) == "Cc" for character in intention):
                raise InvalidFocusSessionDraftError(
                    "temporary intention cannot contain control characters"
                )
            elif len(intention) > MAX_INTENTION_LENGTH:
                raise InvalidFocusSessionDraftError(
                    "temporary intention cannot exceed 240 characters"
                )
        object.__setattr__(self, "temporary_intention", intention)
        for field_name in (
            "start_in_fullscreen",
            "show_quotes",
            "play_completion_sound",
            "overtime_enabled",
            "start_ritual_enabled",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise InvalidFocusSessionDraftError(f"{field_name} must be a bool")
