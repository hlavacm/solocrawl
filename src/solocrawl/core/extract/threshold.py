"""Shared thresholds for deciding when extracted content is too sparse."""

from __future__ import annotations

MIN_MEANINGFUL_CONTENT_CHARS = 80


def is_content_too_short(text: str | None) -> bool:
    """Return True when extracted text is too short to be useful main content."""
    if not text:
        return True
    stripped = text.strip()
    if len(stripped) < MIN_MEANINGFUL_CONTENT_CHARS:
        return True
    alpha = sum(1 for char in stripped if char.isalnum())
    return alpha < MIN_MEANINGFUL_CONTENT_CHARS // 2
