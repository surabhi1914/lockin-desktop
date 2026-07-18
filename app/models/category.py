"""Immutable permanent category model and normalization rules."""

from dataclasses import dataclass
from unicodedata import category as unicode_category

from app.core.errors import ValidationError
from app.core.ids import canonicalize_uuid
from app.core.time_utils import format_utc, parse_utc
from app.models.errors import CategoryError

MAX_CATEGORY_NAME_LENGTH = 60
MAX_CATEGORY_ICON_LENGTH = 16


def _contains_control(value: str) -> bool:
    return any(unicode_category(character) == "Cc" for character in value)


def normalize_category_name(value: str) -> str:
    """Trim and collapse whitespace while retaining user-facing capitalization."""
    if not isinstance(value, str):
        raise CategoryError("category name must be text")
    if _contains_control(value):
        raise CategoryError("category name cannot contain control characters")
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise CategoryError("category name cannot be empty")
    if len(normalized) > MAX_CATEGORY_NAME_LENGTH:
        raise CategoryError("category name cannot exceed 60 characters")
    return normalized


def category_uniqueness_key(value: str) -> str:
    return normalize_category_name(value).casefold()


@dataclass(frozen=True, slots=True)
class Category:
    """One permanent category with a stable canonical identifier."""

    category_id: str
    category_name: str
    category_icon: str | None
    is_active: bool
    created_at_utc: str
    updated_at_utc: str

    def __post_init__(self) -> None:
        try:
            canonical_id = canonicalize_uuid(self.category_id)
        except ValidationError as exc:
            raise CategoryError(str(exc)) from exc
        if canonical_id != self.category_id:
            raise CategoryError("category_id must be a canonical lowercase UUID")
        object.__setattr__(self, "category_name", normalize_category_name(self.category_name))
        if not isinstance(self.is_active, bool):
            raise CategoryError("is_active must be a bool")
        icon = self.category_icon
        if icon is not None:
            if not isinstance(icon, str):
                raise CategoryError("category icon must be text or None")
            icon = icon.strip()
            if not icon:
                icon = None
            elif _contains_control(icon):
                raise CategoryError("category icon cannot contain control characters")
            elif len(icon) > MAX_CATEGORY_ICON_LENGTH:
                raise CategoryError("category icon cannot exceed 16 characters")
        object.__setattr__(self, "category_icon", icon)
        self._validate_timestamp(self.created_at_utc, "created_at_utc")
        self._validate_timestamp(self.updated_at_utc, "updated_at_utc")

    @property
    def normalized_name(self) -> str:
        return self.category_name.casefold()

    @staticmethod
    def _validate_timestamp(value: str, label: str) -> None:
        try:
            parsed = parse_utc(value)
        except ValidationError as exc:
            raise CategoryError(f"{label}: {exc}") from exc
        if format_utc(parsed) != value:
            raise CategoryError(f"{label} must use canonical Phase 0 UTC format")
