"""Helpers to keep frontmatter fields Quartz-friendly and Unicode-safe."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import List

__all__ = ["sanitize_frontmatter_value", "sanitize_frontmatter_list"]

# Collapse any run of whitespace (spaces, tabs, or newlines) to a single space
_WHITESPACE_PATTERN = re.compile(r"\s+")

# Allow common punctuation that won't break YAML while preserving multilingual text
_ALLOWED_PUNCTUATION = {"-", "_", ",", ".", "'", "’", "(", ")", ":", "/"}


def _is_allowed_character(character: str) -> bool:
    """Return True if the character is safe to keep in frontmatter values."""

    return character.isalnum() or character.isspace() or character in _ALLOWED_PUNCTUATION


def sanitize_frontmatter_value(value: str | None) -> str:
    """Normalize a frontmatter value while preserving non-Latin characters."""

    if value is None:
        return ""

    normalized = unicodedata.normalize("NFKC", str(value))
    normalized = _WHITESPACE_PATTERN.sub(" ", normalized)

    cleaned = "".join(ch for ch in normalized if _is_allowed_character(ch))
    return " ".join(cleaned.split())


def sanitize_frontmatter_list(items: Iterable[str] | None) -> List[str]:
    """Sanitize an iterable of frontmatter items and drop empties."""

    if not items:
        return []

    sanitized = [sanitize_frontmatter_value(item) for item in items if item is not None]
    return [item for item in sanitized if item]