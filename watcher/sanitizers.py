"""Utilities for cleaning frontmatter data to keep YAML compatible."""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import List

__all__ = ["sanitize_frontmatter_value", "sanitize_frontmatter_list"]


_THE_PATTERN = re.compile(r"\bthe\b", re.IGNORECASE)
_DISALLOWED_PATTERN = re.compile(r"[^A-Za-z0-9 ]+")


def sanitize_frontmatter_value(value: str | None) -> str:
    """Remove special characters and filler words from a frontmatter value.

    This keeps values YAML friendly by stripping symbols like ``@`` and trimming
    the standalone word "the" which causes noisy or duplicate entities.
    """
    if value is None:
        return ""

    cleaned = _DISALLOWED_PATTERN.sub(" ", str(value))
    cleaned = _THE_PATTERN.sub(" ", cleaned)
    return " ".join(cleaned.split())


def sanitize_frontmatter_list(items: Iterable[str] | None) -> List[str]:
    """Sanitize an iterable of frontmatter items and drop empties."""
    if not items:
        return []

    sanitized = [sanitize_frontmatter_value(item) for item in items if item is not None]
    return [item for item in sanitized if item]
