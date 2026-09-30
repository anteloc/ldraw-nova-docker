"""The model collection: every .mpd/.ldr/.dat directly in data/generated.

Each model has two siblings with the same base name, both made with LeoCAD:
  <name>.png  its snapshot, rendered from the home view
  <name>.csv  its bill of materials (BOM), which also gives the part count
Missing ones are made in the background, one model at a time, whenever
something asks for them (the My Models page, a chat that references the model).
A failed one isn't retried until the model file changes.

An optional third sibling, <name>.md, is whatever its author wants to say
about the model (the prompt that made it, say), shown under Info.

The separate Gallery page shows models baked into the image (models-gallery/
in the repo), which ship with their siblings. The collections are independent.
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Iterable, Optional

import render
from ldraw import title_of
from leocad_render import bom_part_count, bom_path_for, list_models, snapshot_path_for

log = logging.getLogger("gallery")

# kind -> (sibling path for a model, coroutine that makes it)
ARTIFACTS = {
    "snapshot": (snapshot_path_for, lambda model: render.render_snapshot(model, only_if_missing=True)),
    "bom": (bom_path_for, lambda model: render.export_bom(model, only_if_missing=True)),
}

_queue: list[Path] = []
_current: Optional[Path] = None
_failed: dict[tuple[Path, str], tuple[float, str]] = {}   # (model, kind) -> (model mtime when it failed, error)
_task: Optional[asyncio.Task] = None
publishing: set[Path] = set()


def description_of(path: Path) -> str:
    """The model's title line (line 2 of an .mpd, line 1 of a single-file model)."""
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            return title_of(line for _, line in zip(range(40), fh))
    except OSError:
        return ""


def info_path_for(model: Path) -> Path:
    """A model's notes: the sibling .md with the same base name (car.mpd -> car.md)."""
    return model.with_suffix(".md")


def info_heading_of(model: Path) -> Optional[str]:
    """Text of the first ATX H2 in a model's notes, excluding fenced code."""
    fence = ""
    try:
        with info_path_for(model).open(encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
                if fence:
                    if (marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence)
                            and not marker[2].strip()):
                        fence = ""
                    continue
                if marker and (marker[1][0] != "`" or "`" not in marker[2]):
                    fence = marker[1]
                    continue
                heading = re.match(r"^ {0,3}##(?:[ \t]+(.*)|[ \r\n]*$)", line)
                if heading:
                    return re.sub(r"[ \t]+#+[ \t]*$", "", heading[1] or "").strip() or None
    except OSError:
        pass
    return None


def part_count(model: Path) -> Optional[int]:
    """Total parts, from the model's BOM (None until the BOM exists)."""
    bom = bom_path_for(model)
    return bom_part_count(bom) if bom.exists() else None


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _gave_up(model: Path, kind: str) -> bool:
    failed = _failed.get((model, kind))
    return failed is not None and failed[0] == _mtime(model)


def _missing(model: Path) -> list[str]:
    return [kind for kind, (path_for, _make) in ARTIFACTS.items()
            if not path_for(model).exists() and not _gave_up(model, kind)]


def ensure_artifacts(models: Iterable[Path]) -> None:
    """Queue models missing a snapshot or BOM and start the worker if idle."""
    global _task
    for model in models:
        if model != _current and model not in _queue and _missing(model):
            _queue.append(model)
    if _queue and (_task is None or _task.done()):
        _task = asyncio.create_task(_work_queue())


async def _work_queue() -> None:
    global _current
    while _queue:
        model = _queue.pop(0)
        _current = model
        try:
            for kind in _missing(model):
                if not model.exists():
                    break
                try:
                    log.info("making %s for %s", kind, model.name)
                    await ARTIFACTS[kind][1](model)
                    _failed.pop((model, kind), None)
                except Exception as exc:  # noqa: BLE001 - shown on the My Models page
                    _failed[(model, kind)] = (_mtime(model), render.describe_error(exc))
                    log.warning("%s of %s failed: %s", kind, model.name, _failed[(model, kind)][1])
        finally:
            _current = None


def status_of(model: Path, kind: str = "snapshot") -> tuple[str, Optional[str]]:
    """ready | rendering | queued | failed (with the error) for one of the model's siblings."""
    if ARTIFACTS[kind][0](model).exists():
        return "ready", None
    if model == _current:
        return "rendering", None
    if _gave_up(model, kind):
        return "failed", _failed[(model, kind)][1]
    return "queued", None


def collection(folder: Path) -> list[Path]:
    """The models in the collection, newest first."""
    return sorted(list_models(folder), key=_mtime, reverse=True)


def forget(model: Path) -> None:
    """Remove a deleted model from pending preview work and error state."""
    _queue[:] = [path for path in _queue if path != model]
    for key in list(_failed):
        if key[0] == model:
            _failed.pop(key)
