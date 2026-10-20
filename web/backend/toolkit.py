"""Container integration for the unchanged, standalone ldraw-nova checkout."""
from __future__ import annotations

from pathlib import Path

import settings
import sandbox
import environment_config


# Supply the plan format after instructions.md (about 7 KB). Category guides
# and the CLI reference remain available through tools, read on demand.
BUILDER_GUIDES = (
    "docs/agent/plans.md",
)


def root() -> Path:
    path = settings.TOOLKIT_DIR
    if not (path / "instructions.md").is_file() or not (path / ".venv/bin/python").exists():
        raise ValueError("LDraw toolkit is missing. Rebuild with docker compose up -d --build (requires ../ldraw-nova).")
    return path


def workspace(store, chat_id: str) -> Path:
    """A repository-shaped cwd; source resources stay shared and read-only.

    ROOT in the upstream Python package resolves to the installed checkout,
    preserving its data paths and cache. Relative output paths are chat-local.
    """
    source = root()
    cwd = store.chat_dir(chat_id) / "workspace"
    cwd.mkdir(parents=True, exist_ok=True)
    output = store.work_dir(chat_id)
    output.mkdir(parents=True, exist_ok=True)
    sandbox.give_to_agent(output)
    for entry in source.iterdir():
        if entry.name in {"output", ".git", ".env"} or entry.name.startswith(".env."):
            continue
        link = cwd / entry.name
        if not link.exists() and not link.is_symlink():
            link.symlink_to(entry, target_is_directory=entry.is_dir())
    link = cwd / "output"
    if not link.exists() and not link.is_symlink():
        link.symlink_to(output, target_is_directory=True)
    return cwd


def environment() -> dict[str, str]:
    source = root()
    env = environment_config.snapshot()
    return {
        "PATH": f"{source / '.venv/bin'}:{sandbox.SCRIPTS_DIR}:/usr/local/bin:/usr/bin:/bin",
        # Avoid the backend's old ldraw.py shadowing pyldraw3's `ldraw` package.
        "PYTHONPATH": f"{source}:/app",
        # Rosetta can create a root-owned ~/.cache before privileges drop on
        # Apple Silicon. Use the builder's explicitly writable derived cache.
        "XDG_CACHE_HOME": str(source / ".cache"),
        "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "LDRAW_DIR": env.get("LDRAW_DIR") or env.get("LDRAWDIR") or str(settings.LDRAW_DIR),
    }


def instructions() -> str:
    return _read_guide(root(), "instructions.md")


def _read_guide(source: Path, path: str) -> str:
    try:
        return (source / path).read_text()
    except FileNotFoundError:
        raise ValueError(
            f"LDraw toolkit guide is missing: {path}. The web app and ../ldraw-nova "
            "must use matching instructions. Rebuild with docker compose up -d --build."
        ) from None


def builder_guides() -> str:
    source = root()
    return "\n\n".join(f"--- {path} (complete) ---\n{_read_guide(source, path)}" for path in BUILDER_GUIDES)
