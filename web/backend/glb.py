"""On-demand .glb export with mpd2glb (https://github.com/anteloc/mpd2glb).

Uncompressed glTF binary, keeping LDraw metadata on every node (description,
part file, colour, building step, ...). A big model can take a minute (the
image runs under emulation on Apple Silicon), so results are cached per model
version (path + mtime + size) and concurrent requests for the same model
share one conversion. The cache lives in the container's /tmp, not in
data/generated: .glb files are made when asked for, not kept with the models.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

import settings

# scripts/mpd2glb.sh, on PATH in the image: the one way to run mpd2glb, so how
# it runs (runtime, install location) can change without touching callers.
MPD2GLB = os.environ.get("LEOCAD_MPD2GLB", "mpd2glb.sh")
CACHE_DIR = Path(os.environ.get("LEOCAD_GLB_CACHE_DIR", "/tmp/glb-cache"))
TIMEOUT_SECONDS = 900

_limit = asyncio.Semaphore(2)                 # node is CPU- and memory-hungry on big models
_inflight: dict[Path, asyncio.Task] = {}


class GlbError(Exception):
    pass


def _cached_path(model: Path) -> Path:
    stat = model.stat()
    key = hashlib.sha1(str(model.resolve()).encode()).hexdigest()[:16]
    return CACHE_DIR / f"{key}-{stat.st_mtime_ns}-{stat.st_size}.glb"


async def export_glb(model: Path) -> Path:
    """The model as .glb, converting it unless this version is already cached."""
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
