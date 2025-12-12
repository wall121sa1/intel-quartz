"""Utilities for cleaning frontmatter data to keep YAML compatible."""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import List

__all__ = ["sanitize_frontmatter_value", "sanitize_frontmatter_list"]

_THE_PATTERN = re.compile(r"\bthe\b", re.IGNORECASE)
# \s+ matches any whitespace characters (space, tab, newline, return, formfeed)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_DISALLOWED_PATTERN = re.compile(r"[^A-Za-z0-9 ]+")


def sanitize_frontmatter_value(value: str | None) -> str:
    """Remove special characters, newlines, and filler words from a frontmatter value."""
    if value is None:
        return ""

    text = str(value)
    
    # 1. Collapse ALL whitespace (newlines, tabs) into a single space
    text = _WHITESPACE_PATTERN.sub(" ", text)

    # 2. Remove disallowed characters (keep only alphanumeric and space)
    cleaned = _DISALLOWED_PATTERN.sub(" ", text)
    
    # 3. Remove 'the' word to reduce duplicates
    cleaned = _THE_PATTERN.sub(" ", cleaned)
    
    # 4. Trim leading/trailing spaces
    return " ".join(cleaned.split())


def sanitize_frontmatter_list(items: Iterable[str] | None) -> List[str]:
    """Sanitize an iterable of frontmatter items and drop empties."""
    if not items:
        return []

    sanitized = [sanitize_frontmatter_value(item) for item in items if item is not None]
    return [item for item in sanitized if item]