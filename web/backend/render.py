"""Async front for leocad_render: one render at a time, since the container has
a single Xvfb display (see README "Concurrency")."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from collections import Counter
from pathlib import Path

import leocad_render

_lock = asyncio.Lock()
_pending = Counter()


def is_busy(model: Path) -> bool:
    return _pending[model.resolve()] > 0


@asynccontextmanager
async def _rendering(model: Path):
    path = model.resolve()
    _pending[path] += 1
    try:
        async with _lock:
            yield
    finally:
        _pending[path] -= 1
        if not _pending[path]:
            del _pending[path]


async def render(model_path: Path, output_path: Path, **kwargs) -> Path:
    async with _rendering(model_path):
        return await asyncio.to_thread(leocad_render.render_image, model_path, output_path, **kwargs)


async def render_snapshot(model_path: Path, only_if_missing: bool = False) -> Path:
    """The model's sibling .png, from LeoCAD's home view. With `only_if_missing`,
    skip it if the snapshot appeared while waiting for the display."""
    async with _rendering(model_path):
        png = leocad_render.snapshot_path_for(model_path)
        if only_if_missing and png.exists():
            return png
        return await asyncio.to_thread(leocad_render.render_snapshot, model_path)


async def export_bom(model_path: Path, only_if_missing: bool = False) -> Path:
    """The model's sibling .csv bill of materials, from LeoCAD's CSV export."""
    async with _rendering(model_path):
        bom = leocad_render.bom_path_for(model_path)
        if only_if_missing and bom.exists():
            return bom
        return await asyncio.to_thread(leocad_render.export_bom, model_path)


def describe_error(exc: Exception) -> str:
    stderr = getattr(exc, "stderr", None)
    if stderr:
        # LeoCAD prints Qt noise first; the useful part is the tail.
        return f"{exc.__class__.__name__}: {stderr.strip()[-600:]}"
    return f"{exc.__class__.__name__}: {exc}"
