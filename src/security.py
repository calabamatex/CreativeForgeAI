"""Security utilities: input sanitization, validation helpers, and constants.

This module centralizes security-critical functions so they can be reused
across the API layer and GenAI backends.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Maximum prompt length sent to any AI backend (chars).
MAX_PROMPT_LENGTH: int = 4_000

#: Allowed file extensions for user uploads.
ALLOWED_UPLOAD_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".docx", ".txt", ".json", ".yaml", ".yml"}
)

#: Maximum upload file size in bytes (10 MB).
MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

#: Regex that matches characters considered *control characters* for our
#: purposes.  We strip C0/C1 controls except common whitespace (tab, newline,
#: carriage return).
_CONTROL_CHAR_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)

#: UUID v4 pattern for path parameter validation.
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


# ---------------------------------------------------------------------------
# Prompt sanitization
# ---------------------------------------------------------------------------


def sanitize_prompt(text: str, *, max_length: int = MAX_PROMPT_LENGTH) -> str:
    """Sanitize a prompt before sending it to an AI backend.

    1. Strip Unicode control characters (C0/C1) except tab/newline/CR.
    2. Normalize Unicode to NFC form to prevent homoglyph attacks.
    3. Truncate to *max_length* characters.
    4. Strip leading/trailing whitespace.

    Args:
        text: Raw prompt text.
        max_length: Maximum allowed character count.

    Returns:
        Cleaned prompt string.
    """
    if not text:
        return ""

    # Strip control characters
    cleaned = _CONTROL_CHAR_RE.sub("", text)

    # Normalize Unicode
    cleaned = unicodedata.normalize("NFC", cleaned)

    # Truncate
    if len(cleaned) > max_length:
        logger.warning(
            "security.prompt_truncated",
            original_length=len(text),
            max_length=max_length,
        )
        cleaned = cleaned[:max_length]

    return cleaned.strip()


# ---------------------------------------------------------------------------
# File upload validation
# ---------------------------------------------------------------------------


def validate_upload_extension(filename: str) -> str:
    """Validate that a filename has an allowed extension.

    Args:
        filename: Original filename from the upload.

    Returns:
        The lowercased extension (e.g. ``".pdf"``).

    Raises:
        ValueError: If the extension is not in the allow-list.
    """
    if not filename:
        raise ValueError("Filename must not be empty")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError(
            f"File type '{ext}' is not allowed. "
            f"Accepted types: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}"
        )
    return ext


def validate_upload_size(size_bytes: int) -> None:
    """Validate that the upload size is within limits.

    Args:
        size_bytes: Size of the uploaded content in bytes.

    Raises:
        ValueError: If the file exceeds ``MAX_UPLOAD_SIZE_BYTES``.
    """
    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
        max_mb = MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        actual_mb = size_bytes / (1024 * 1024)
        raise ValueError(
            f"File size {actual_mb:.1f} MB exceeds maximum of {max_mb:.0f} MB"
        )


# ---------------------------------------------------------------------------
# Path traversal protection
# ---------------------------------------------------------------------------


def validate_safe_path(user_path: str, base_dir: str | Path) -> Path:
    """Resolve *user_path* relative to *base_dir* and ensure it stays within bounds.

    Args:
        user_path: User-supplied path component.
        base_dir: Trusted base directory.

    Returns:
        Resolved ``Path`` that is guaranteed to be under *base_dir*.

    Raises:
        ValueError: If the resolved path escapes *base_dir* or contains
            dangerous sequences.
    """
    if not user_path:
        raise ValueError("Path must not be empty")

    # Reject obvious traversal sequences before resolving
    if ".." in user_path:
        raise ValueError("Path must not contain '..'")

    base = Path(base_dir).resolve()
    resolved = (base / user_path).resolve()

    if not str(resolved).startswith(str(base)):
        raise ValueError("Path escapes the allowed directory")

    return resolved


# ---------------------------------------------------------------------------
# UUID validation
# ---------------------------------------------------------------------------


def is_valid_uuid(value: str) -> bool:
    """Return ``True`` if *value* is a valid UUID v4 string."""
    return bool(UUID_RE.match(value))
