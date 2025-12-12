"""Clean existing markdown frontmatter to keep Quartz compatible."""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Dict, Tuple
import sys

import frontmatter

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sanitizers import sanitize_frontmatter_list, sanitize_frontmatter_value

SCRIPT_DIR = Path(__file__).resolve().parent


def _normalize_root(path_str: str) -> Path:
    """Convert the provided path to an absolute ``Path``.

    UNC-style paths (e.g., ``\\\\wsl.localhost\\...``) are converted to
    forward-slash notation so they can be traversed on Linux hosts. Relative
    paths are resolved against the current working directory to work both on
    the host and inside the Docker container image where ``/app`` is the
    default workdir.
    """

    normalized_str = path_str
    if path_str.startswith("\\\\"):
        normalized_str = path_str.replace("\\", "/")

    candidate = Path(normalized_str).expanduser()
    if candidate.is_absolute():
        return candidate

    return (Path.cwd() / candidate).resolve()


def _yaml_module():
    spec = importlib.util.find_spec("yaml")
    if spec is None:
        return None

    return importlib.import_module("yaml")


def _compose_candidates() -> list[Path]:
    candidates = [
        Path.cwd() / "docker-compose.yml",
        Path.cwd() / "docker-compose.yaml",
        SCRIPT_DIR / "docker-compose.yml",
        SCRIPT_DIR / "docker-compose.yaml",
        SCRIPT_DIR.parent / "docker-compose.yml",
        SCRIPT_DIR.parent / "docker-compose.yaml",
        SCRIPT_DIR.parent / "watcher" / "docker-compose.yml",
        SCRIPT_DIR.parent / "watcher" / "docker-compose.yaml",
    ]

    seen: set[Path] = set()
    unique_candidates: list[Path] = []
    for path in candidates:
        if path not in seen:
            unique_candidates.append(path)
            seen.add(path)
    return unique_candidates


def _find_compose_file(verbose: bool) -> Path | None:
    for candidate in _compose_candidates():
        if candidate.exists():
            return candidate

    if verbose:
        print(
            "⚠️ Unable to locate docker-compose.yml near the current working "
            "directory or script location; skipping compose-based defaults."
        )
    return None


def _load_compose(verbose: bool) -> Dict[str, Any]:
    yaml = _yaml_module()
    if yaml is None:
        if verbose:
            print("⚠️ PyYAML not installed; unable to load docker-compose.yml for defaults")
        return {}

    compose_path = _find_compose_file(verbose)
    if compose_path is None:
        return {}

    try:
        content = compose_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
    except Exception as exc:  # noqa: BLE001
        if verbose:
            print(f"⚠️ Unable to parse docker-compose.yml: {exc}")
        return {}

    if not isinstance(data, dict):
        if verbose:
            print("⚠️ docker-compose.yml did not parse to a dictionary")
        return {}

    return data


def _extract_vault_mounts(compose: Dict[str, Any]) -> list[tuple[str | None, str | None]]:
    mounts: list[tuple[str | None, str | None]] = []

    services = compose.get("services", {}) or {}
    for service_key in ("watcher", "watcher-worker", "quartz"):
        service = services.get(service_key)
        if not isinstance(service, dict):
            continue

        for volume in service.get("volumes", []) or []:
            source: str | None = None
            target: str | None = None
            if isinstance(volume, str):
                parts = volume.split(":", 2)
                source = parts[0] if parts else None
                target = parts[1] if len(parts) > 1 else None
            elif isinstance(volume, dict):
                source = volume.get("source")
                target = volume.get("target") or volume.get("destination")
            if source and "vault" in source:
                mounts.append((source, target))

        env = service.get("environment", {}) if isinstance(service, dict) else {}
        env_value = None
        if isinstance(env, dict):
            env_value = env.get("VAULT_ROOT")
        elif isinstance(env, list):
            for item in env:
                if isinstance(item, str) and item.startswith("VAULT_ROOT="):
                    env_value = item.partition("=")[2]
                    break
        if env_value:
            mounts.append((None, env_value))

    volumes = compose.get("volumes")
    if isinstance(volumes, dict):
        for volume_name in volumes:
            if "vault" in volume_name:
                mounts.append((volume_name, None))

    return mounts


def _environment_roots(verbose: bool) -> list[Path]:
    roots: list[Path] = []
    for key in ("VAULT_ROOT", "VAULT_PATH"):
        value = os.environ.get(key)
        if not value:
            continue

        candidate = _normalize_root(value)
        if candidate.exists():
            roots.append(candidate)
        elif verbose:
            print(f"⚠️ Ignoring missing {key} path: {candidate}")

    return roots


def _docker_mountpoint(volume_name: str, verbose: bool) -> Path | None:
    try:
        result = subprocess.run(
            ["docker", "volume", "inspect", volume_name],
            capture_output=True,
            check=True,
            text=True,
        )
    except FileNotFoundError:
        if verbose:
            print("⚠️ Docker CLI not available; cannot resolve volume mount point")
        return None
    except subprocess.CalledProcessError as exc:
        if verbose:
            print(f"⚠️ docker volume inspect failed for {volume_name}: {exc.stderr.strip()}")
        return None

    try:
        info = json.loads(result.stdout)
        mountpoint = info[0].get("Mountpoint") if info else None
        return Path(mountpoint) if mountpoint else None
    except Exception as exc:  # noqa: BLE001
        if verbose:
            print(f"⚠️ Unable to parse docker volume inspect output: {exc}")
        return None


def _discover_default_roots(verbose: bool) -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()

    def _add_root(candidate: Path) -> None:
        resolved = candidate.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        if resolved.exists():
            roots.append(resolved)
        elif verbose:
            print(f"⚠️ Ignoring unavailable mount target: {resolved}")

    for env_root in _environment_roots(verbose):
        _add_root(env_root)

    compose = _load_compose(verbose)
    if not compose:
        return roots

    for volume_name, target in _extract_vault_mounts(compose):
        if target:
            _add_root(_normalize_root(target))

        if volume_name:
            mountpoint = _docker_mountpoint(volume_name, verbose)
            if mountpoint is not None:
                _add_root(mountpoint)

    if not roots and verbose:
        print("⚠️ No vault-like volume or mount path found in docker-compose.yml")

    return roots

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
        "roots",
        metavar="ROOT",
        nargs="*",
        help=(
            "Root directory (or directories) to scan for markdown files. Defaults to the "
            "VAULT_ROOT/VAULT_PATH environment variable or vault mount discovered from "
            "docker-compose.yml."
        ),
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
    target_roots = args.roots
    if not target_roots:
        discovered = _discover_default_roots(args.verbose)
        target_roots = [str(path) for path in discovered]
        if not target_roots and args.verbose:
            print(
                "⚠️ No default roots discovered from docker-compose.yml; "
                "provide ROOT arguments explicitly."
            )

    markdown_files = []
    for root in target_roots:
        base_path = _normalize_root(root)
        if not base_path.exists():
            if args.verbose:
                print(f"⚠️ Skipping missing path: {base_path}")
            continue
        markdown_files.extend(p for p in base_path.rglob("*.md") if p.is_file())
    markdown_files = sorted(set(markdown_files))

    if not markdown_files:
        print("No markdown files found in target directories.")
        return

    updated = 0
    for md_file in markdown_files:
        if _process_file(md_file, args.dry_run, args.verbose):
            updated += 1

    print(f"Finished scanning {len(markdown_files)} files; updated {updated}.")


if __name__ == "__main__":
    main()
