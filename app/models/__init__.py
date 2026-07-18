"""Immutable application models and typed domain errors."""

from app.models.category import Category, normalize_category_name
from app.models.errors import (
    CategoryError,
    CategoryNotFoundError,
    CategoryPersistenceError,
    DuplicateCategoryError,
    FocusSessionAlreadyActiveError,
    InvalidFocusSessionDraftError,
    NoActiveFocusSessionError,
    ProtectedCategoryError,
)
from app.models.focus_session_draft import FocusSessionDraft
from app.models.focus_summary import FocusSummary, FocusSummaryStatus

__all__ = [
    "Category",
    "CategoryError",
    "CategoryNotFoundError",
    "CategoryPersistenceError",
    "DuplicateCategoryError",
    "FocusSessionAlreadyActiveError",
    "FocusSessionDraft",
    "FocusSummary",
    "FocusSummaryStatus",
    "InvalidFocusSessionDraftError",
    "NoActiveFocusSessionError",
    "ProtectedCategoryError",
    "normalize_category_name",
]
