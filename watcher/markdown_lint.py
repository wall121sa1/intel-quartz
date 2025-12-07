#!/usr/bin/env python3
"""
Markdown hygiene checker for docs/notes content.

Scans markdown files for control characters, mixed line endings,
frontmatter mistakes, and missing headings or titles.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import yaml

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    import tomli as tomllib  # type: ignore[no-redef]

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIRECTORIES = ("docs", "notes", "examples")
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
FRONTMATTER_BLOCK_PATTERN = re.compile(r"(---|\+\+\+)\s*\r?\n(.*?)\r?\n\1\s*(\r?\n|$)", re.DOTALL)
HEADING_ATX_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+\S", re.MULTILINE)
HEADING_SETEXT_PATTERN = re.compile(r"^(?P<title>.+)\r?\n(=+|-+)\s*$", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint markdown files for common content issues.")
    parser.add_argument(
        "paths",
        metavar="PATH",
        nargs="*",
        help="Directories to scan (defaults to docs, notes, examples)",
    )
    return parser.parse_args()


def gather_markdown_files(paths: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for path_str in paths:
        root = (REPO_ROOT / path_str).resolve()
        if not root.exists():
            continue
        files.extend(p for p in root.rglob("*.md") if p.is_file())
    return sorted(set(files))


def detect_control_characters(content: str) -> List[str]:
    issues: List[str] = []
    for match in CONTROL_CHAR_PATTERN.finditer(content):
        index = match.start()
        snippet = content[max(0, index - 10) : min(len(content), index + 10)].replace("\n", "\\n")
        codepoint = ord(match.group(0))
        issues.append(f"Control character U+{codepoint:04x} near \"{snippet}\"")
    return issues


def detect_mixed_line_endings(content: str) -> List[str]:
    crlf = len(re.findall(r"\r\n", content))
    lf = len(re.findall(r"(?<!\r)\n", content))
    if crlf and lf:
        return ["Mixed LF and CRLF line endings detected"]
    return []


def parse_frontmatter(block: str, delimiter: str) -> Dict:
    if delimiter == "---":
        parsed = yaml.safe_load(block) or {}
    else:
        parsed = tomllib.loads(block) or {}
    return parsed if isinstance(parsed, dict) else {}


def detect_frontmatter(content: str) -> Tuple[List[str], Dict, int]:
    issues: List[str] = []
    matches = list(FRONTMATTER_BLOCK_PATTERN.finditer(content))

    if content.startswith(("---", "+++")) and not matches:
        issues.append("Frontmatter opening delimiter found without a closing '---' or '+++'")
        return issues, {}, 0

    if not matches:
        return issues, {}, 0

    if matches[0].start() != 0:
        issues.append("Frontmatter must appear at the start of the document")

    if len(matches) > 1:
        issues.append("Multiple frontmatter blocks detected")

    primary = matches[0]
    delimiter = primary.group(1)
    block = primary.group(2)
    try:
        data = parse_frontmatter(block, delimiter)
    except Exception as exc:  # pragma: no cover - defensive parsing
        issues.append(f"Frontmatter parsing error: {exc}")
        data = {}

    return issues, data, primary.end()


def detect_missing_heading(content: str, frontmatter_end: int, frontmatter_data: Dict) -> List[str]:
    remaining = content[frontmatter_end:]
    has_atx = bool(HEADING_ATX_PATTERN.search(remaining))
    has_setext = bool(HEADING_SETEXT_PATTERN.search(remaining))
    if not (has_atx or has_setext) and not frontmatter_data.get("title"):
        return ["Document is missing both a heading and a frontmatter title"]
    return []


def analyze_file(path: Path) -> List[str]:
    content = path.read_text(encoding="utf-8", errors="replace")
    issues: List[str] = []
    issues.extend(detect_control_characters(content))
    issues.extend(detect_mixed_line_endings(content))
    fm_issues, fm_data, fm_end = detect_frontmatter(content)
    issues.extend(fm_issues)
    issues.extend(detect_missing_heading(content, fm_end, fm_data))
    return issues


def main() -> int:
    args = parse_args()
    paths = args.paths or DEFAULT_DIRECTORIES
    markdown_files = gather_markdown_files(paths)

    if not markdown_files:
        print("No markdown files found in target directories.")
        return 0

    findings = []
    for md_file in markdown_files:
        issues = analyze_file(md_file)
        if issues:
            findings.append((md_file, issues))

    if not findings:
        print(f"Checked {len(markdown_files)} markdown files. No issues found.")
        return 0

    print("Markdown quality check found issues:\n")
    for path, issues in findings:
        rel_path = path.relative_to(REPO_ROOT)
        print(f"- {rel_path}")
        for issue in issues:
            print(f"  • {issue}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
