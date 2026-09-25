"""Path helpers shared by the HTTP file routes and the agent tools."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional


def safe_join(root: Path, rel: str, case_insensitive: bool = False) -> Optional[Path]:
    """Resolve `rel` under `root`, or None if it would escape `root`.

    Rejects `..`, absolute paths and symlinks pointing outside the root.
    With `case_insensitive`, a missing path is retried component by component
    ignoring case (LDraw references are case-insensitive, Linux isn't).
    """
    rel = rel.replace("\\", "/").lstrip("/")
    root = root.resolve()
    candidate = (root / rel).resolve()
    if not _inside(candidate, root):
        return None
    if case_insensitive and not candidate.exists():
        found = _case_insensitive_lookup(str(root), rel)
        if found is None:
            return candidate          # caller reports "not found"
        candidate = found.resolve()
        if not _inside(candidate, root):
            return None
    return candidate


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _case_insensitive_lookup(root: str, rel: str) -> Optional[Path]:
    current = root
    for part in [p for p in rel.split("/") if p and p != "."]:
        if part == "..":
            return None
        match = _lower_listing(current).get(part.lower())
        if match is None:
            return None
        current = os.path.join(current, match)
    return Path(current)


@lru_cache(maxsize=4096)
def _lower_listing(directory: str) -> dict[str, str]:
    # Only used on baked-in, read-only trees (the LDraw library), so caching
    # directory listings forever is safe.
    try:
        return {name.lower(): name for name in os.listdir(directory)}
    except OSError:
        return {}


def rel_to(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
