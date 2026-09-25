"""Async front for leocad_render.render_image(): one render at a time, since
the container has a single Xvfb display (see README "Concurrency")."""
from __future__ import annotations

import asyncio
from pathlib import Path

from leocad_render import render_image

_lock = asyncio.Lock()


async def render(model_path: Path, output_path: Path, **kwargs) -> Path:
    async with _lock:
        return await asyncio.to_thread(render_image, model_path, output_path, **kwargs)


def describe_error(exc: Exception) -> str:
    stderr = getattr(exc, "stderr", None)
    if stderr:
        # LeoCAD prints Qt noise first; the useful part is the tail.
        return f"{exc.__class__.__name__}: {stderr.strip()[-600:]}"
    return f"{exc.__class__.__name__}: {exc}"
