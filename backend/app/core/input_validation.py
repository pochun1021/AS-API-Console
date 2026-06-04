import re

from app.core.errors import ApiError

_UNSAFE_HTML_PATTERN = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
_UNSAFE_SCRIPT_PATTERN = re.compile(r"<\s*/?\s*script\b", re.IGNORECASE)
_UNSAFE_JAVASCRIPT_URI_PATTERN = re.compile(r"javascript\s*:", re.IGNORECASE)
_UNSAFE_SQL_PATTERN = re.compile(
    r"(?:\bunion\b\s+\bselect\b|\bdrop\b\s+\btable\b|\binsert\b\s+\binto\b|\bdelete\b\s+\bfrom\b|--|/\*)",
    re.IGNORECASE,
)
_UNSAFE_JS_PATTERN = re.compile(
    r"(?:\bfunction\b\s*\(|=>|\balert\s*\(|\bconsole\.[a-zA-Z_]+\s*\()",
    re.IGNORECASE,
)
_ASCII_DIGITS_PATTERN = re.compile(r"^[0-9]+$")


def contains_unsafe_persisted_text(value: str) -> bool:
    return any(
        pattern.search(value)
        for pattern in (
            _UNSAFE_HTML_PATTERN,
            _UNSAFE_SCRIPT_PATTERN,
            _UNSAFE_JAVASCRIPT_URI_PATTERN,
            _UNSAFE_SQL_PATTERN,
            _UNSAFE_JS_PATTERN,
        )
    )


def validate_safe_persisted_text(
    *,
    field_name: str,
    value: str | None,
    required: bool = False,
    allow_empty: bool = True,
) -> str | None:
    if value is None:
        if required:
            raise ApiError("VALIDATION_ERROR", f"{field_name} is required", 422)
        return None

    normalized = str(value).strip()
    if not normalized:
        if required or not allow_empty:
            raise ApiError("VALIDATION_ERROR", f"{field_name} is required", 422)
        return None

    if contains_unsafe_persisted_text(normalized):
        raise ApiError("VALIDATION_ERROR", f"{field_name} contains unsafe syntax", 422)

    return normalized


def parse_ascii_digits(
    *,
    field_name: str,
    value: object,
    allow_zero: bool = True,
) -> int:
    if isinstance(value, bool):
        raise ApiError("VALIDATION_ERROR", f"{field_name} must contain only ASCII digits", 422)
    if isinstance(value, int):
        normalized = str(value)
    elif isinstance(value, str):
        normalized = value.strip()
    else:
        raise ApiError("VALIDATION_ERROR", f"{field_name} must contain only ASCII digits", 422)

    if not normalized or not _ASCII_DIGITS_PATTERN.fullmatch(normalized):
        raise ApiError("VALIDATION_ERROR", f"{field_name} must contain only ASCII digits", 422)

    parsed = int(normalized)
    if not allow_zero and parsed <= 0:
        raise ApiError("VALIDATION_ERROR", f"{field_name} must be positive integer", 422)
    return parsed


def validate_ascii_digits_string(*, field_name: str, value: str | None) -> str:
    normalized = str(value or "").strip()
    if not normalized or not _ASCII_DIGITS_PATTERN.fullmatch(normalized):
        raise ApiError("VALIDATION_ERROR", f"{field_name} must contain only ASCII digits", 422)
    return normalized
