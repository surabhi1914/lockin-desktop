"""UUID generation and canonicalization helpers."""

from uuid import UUID, uuid4, uuid5

from app.core.errors import ValidationError

STARTER_CATEGORY_NAMESPACE = UUID("9967e9df-5870-5bcb-9b35-917642f89ee8")


def new_uuid4() -> str:
    """Return a canonical lowercase UUID4 string."""
    return str(uuid4())


def canonicalize_uuid(value: str) -> str:
    """Validate and canonicalize a UUID string."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("UUID must be a non-empty string")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValidationError(f"Invalid UUID: {value!r}") from exc
    return str(parsed)


def starter_category_uuid(category_name: str) -> str:
    """Return a deterministic UUID5 for a normalized starter category name."""
    normalized = " ".join(category_name.strip().split()).casefold()
    if not normalized:
        raise ValidationError("Category name must not be empty")
    return str(uuid5(STARTER_CATEGORY_NAMESPACE, normalized))
