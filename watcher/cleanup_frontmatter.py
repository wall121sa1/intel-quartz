"""Clean existing markdown frontmatter to keep Quartz compatible."""
from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Dict, Tuple

import frontmatter

from watcher.sanitizers import sanitize_frontmatter_list, sanitize_frontmatter_value

STRING_FIELDS = {
    "title",
    "source",
    "reliability",
    "country",
    "language",
    "feed_type",
}

LIST_FIELDS = {
    "tags",
    "organizations",
    "people",
    "locations",
    "events",
}


def _sanitize_metadata(metadata: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Return sanitized metadata and whether any changes were made."""
    updated = dict(metadata)
    changed = False

    for key in STRING_FIELDS:
        if key not in updated:
            continue
        value = updated.get(key)
        if value is None:
            sanitized = ""
        else:
            sanitized = sanitize_frontmatter_value(value if isinstance(value, str) else str(value))
        if sanitized != value:
            updated[key] = sanitized
            changed = True

    for key in LIST_FIELDS:
        if key not in updated:
            continue
        value = updated.get(key)
        items: Iterable[str] | None = None
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",") if item.strip()]
        elif isinstance(value, Iterable):
            items = value
        sanitized_list = sanitize_frontmatter_list(items)
        if sanitized_list != value:
            updated[key] = sanitized_list
            changed = True

    return changed, updated


def _process_file(path: Path, dry_run: bool, verbose: bool) -> bool:
    """Sanitize a single markdown file. Returns True if modified."""
    try:
        post = frontmatter.load(path)
    except Exception as exc:  # noqa: BLE001
        if verbose:
            print(f"⚠️ Skipping {path}: {exc}")
        return False

    changed, new_metadata = _sanitize_metadata(post.metadata or {})
    if not changed:
        if verbose:
            print(f"✅ {path} already clean")
        return False

    post.metadata = new_metadata
    if dry_run:
        print(f"DRY RUN: Would update {path}")
        return True

    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    print(f"🧹 Updated {path}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root directory to scan for markdown files (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show files that would be updated without writing changes",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print progress for every file"
    )

    args = parser.parse_args()
    base_path = Path(args.root).expanduser().resolve()
    markdown_files = sorted(base_path.rglob("*.md"))

    if not markdown_files:
        print(f"No markdown files found under {base_path}")
        return

    updated = 0
    for md_file in markdown_files:
        if _process_file(md_file, args.dry_run, args.verbose):
            updated += 1

    print(f"Finished scanning {len(markdown_files)} files; updated {updated}.")


if __name__ == "__main__":
    main()
