"""Canonical sibling .glb files, or on-demand export with mpd2glb.

Uncompressed glTF binary, keeping LDraw metadata on every node (description,
part file, colour, building step, ...). A big model can take a minute (the
image runs under emulation on Apple Silicon), so results are cached per model
version (path + mtime + size) and concurrent requests for the same model
share one conversion. The cache lives in the container's /tmp, not in
data/generated. A same-named .glb beside the source model always takes
precedence, including over a previously cached conversion.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

import settings

# scripts/mpd2glb.sh, on PATH in the image: the one way to run mpd2glb, so how
# it runs (runtime, install location) can change without touching callers.
MPD2GLB = os.environ.get("LDRAW_NOVA_MPD2GLB", "mpd2glb.sh")
CACHE_DIR = Path(os.environ.get("LDRAW_NOVA_GLB_CACHE_DIR", "/tmp/glb-cache"))
TIMEOUT_SECONDS = 900

_limit = asyncio.Semaphore(2)                 # node is CPU- and memory-hungry on big models
_inflight: dict[Path, asyncio.Task] = {}


class GlbError(Exception):
    pass


def sibling_glb(model: Path) -> Path | None:
    """An authored alternate in the same directory; never follow an escaping link."""
    candidate = model.with_suffix(".glb")
    if candidate.is_file() and candidate.resolve().parent == model.parent.resolve():
        return candidate
    return None


def cache_files(model: Path) -> list[Path]:
    prefix = hashlib.sha1(str(model.resolve()).encode()).hexdigest()[:16]
    return list(CACHE_DIR.glob(f"{prefix}-*.glb"))


def is_converting(model: Path) -> bool:
    prefix = hashlib.sha1(str(model.resolve()).encode()).hexdigest()[:16] + "-"
    return any(path.name.startswith(prefix) and not task.done() for path, task in _inflight.items())


def _cached_path(model: Path) -> Path:
    stat = model.stat()
    key = hashlib.sha1(str(model.resolve()).encode()).hexdigest()[:16]
    return CACHE_DIR / f"{key}-{stat.st_mtime_ns}-{stat.st_size}.glb"


async def export_glb(model: Path) -> Path:
    """Prefer the sibling GLB, then a cached conversion, then generate one."""
    if sibling := sibling_glb(model):
        return sibling
    out = _cached_path(model)
    if out.exists():
        return out
    task = _inflight.get(out)
    if task is None:
        task = asyncio.create_task(_convert(model, out))
        _inflight[out] = task
        task.add_done_callback(lambda _t: _inflight.pop(out, None))
    # shield: a client that gives up doesn't cancel a conversion others may be waiting for
    return await asyncio.shield(task)


async def _convert(model: Path, out: Path) -> Path:
    async with _limit:
        # An alternate may have been published while this conversion was queued.
        if sibling := sibling_glb(model):
            return sibling
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        partial = out.with_name(out.stem + ".partial.glb")
        proc = await asyncio.create_subprocess_exec(
            MPD2GLB, "-c", "none", "-l", str(settings.LDRAW_DIR), "-o", str(partial), str(model),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=CACHE_DIR,
        )
        try:
            output, _ = await asyncio.wait_for(proc.communicate(), TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            partial.unlink(missing_ok=True)
            raise GlbError(f"mpd2glb took longer than {TIMEOUT_SECONDS} s") from None
        if proc.returncode != 0 or not partial.exists():
            partial.unlink(missing_ok=True)
            tail = output.decode(errors="replace").strip()[-800:]
            raise GlbError(f"mpd2glb failed (exit {proc.returncode}): {tail}")
        partial.replace(out)
        prefix = out.name.split("-", 1)[0]
        for older in CACHE_DIR.glob(f"{prefix}-*.glb"):     # earlier versions of the same model
            if older != out and not older.name.endswith(".partial.glb"):
                older.unlink(missing_ok=True)
        return out
