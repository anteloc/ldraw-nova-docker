"""Tools the agents can call. Schemas are OpenAI function-calling format,
which LiteLLM translates for every provider.

Where things go:
  /data/generated/        finished models (flat) + their .png snapshots: the Models page
  /data/output/<chat>/    the chat's work folder: scripts' cwd, notes, plans, scratch files
  /data/chats/<chat>/renders/   extra renders shown in the chat
"""
from __future__ import annotations

import inspect
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

import ldraw
import render
import sandbox
import settings
from leocad_render import bom_part_count, bom_path_for, list_models, snapshot_path_for
from paths import safe_join
from store import ChatStore

MAX_WRITE_BYTES = 2 * 1024 * 1024


class ToolError(Exception):
    """An error message meant for the agent (it can fix its call and retry)."""


@dataclass
class ToolContext:
    chat_id: str
    store: ChatStore
    emit: Callable[[str, dict], None]

    @property
    def work_dir(self) -> Path:
        return self.store.work_dir(self.chat_id)

    @property
    def chat_dir(self) -> Path:
        return self.store.chat_dir(self.chat_id)


@dataclass
class ToolResult:
    content: str                                          # what the LLM sees
    models: list[dict] = field(default_factory=list)      # model references added to the chat
    images: list[Path] = field(default_factory=list)      # PNGs to show (and send to vision models)


# --- helpers ---------------------------------------------------------------

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "model"


def _next_version(slug: str) -> int:
    pattern = re.compile(rf"{re.escape(slug)}-v(\d+)\.(mpd|ldr|dat)", re.IGNORECASE)
    versions = [int(m.group(1)) for p in list_models(settings.GENERATED_DIR) if (m := pattern.fullmatch(p.name))]
    return max(versions, default=0) + 1


def resolve_path(ctx: ToolContext, path: str, *, write: bool = False) -> Path:
    """Paths the agent may use. Reading: the model collection, its own work
    folder and the reference models. Writing (write_file): only its work folder.
    Relative paths are relative to the work folder."""
    path = (path or "").strip()
    roots = [ctx.work_dir] if write else [ctx.work_dir, settings.GENERATED_DIR, settings.REF_MODELS_DIR]
    if path.startswith("/"):
        for root in roots:
            if path == str(root) or path.startswith(str(root) + "/"):
                resolved = safe_join(root, path[len(str(root)):])
                break
        else:
            raise ToolError(f"{path} is outside the allowed folders: {', '.join(map(str, roots))}")
    else:
        resolved = safe_join(ctx.work_dir, path)
    if resolved is None:
        raise ToolError(f"{path} escapes the allowed folders")
    return resolved


async def publish(ctx: ToolContext, model_path: Path, name: str, warnings: list[str]) -> tuple[dict, str | None]:
    """A model in /data/generated: (re)make its snapshot and BOM, and link it to the chat."""
    render_error = None
    try:
        await render.render_snapshot(model_path)
    except Exception as exc:  # noqa: BLE001 - reported to the agent and the UI
        render_error = render.describe_error(exc)
    try:
        await render.export_bom(model_path)
    except Exception as exc:  # noqa: BLE001 - the Models page retries once the model changes
        warnings = [*warnings, f"BOM export failed: {render.describe_error(exc)}"]
    ref = ctx.store.add_model(ctx.chat_id, name, model_path, warnings)
    ctx.emit("model", {"id": ref["id"], "name": name})
    return ref, render_error


def _collection_state() -> dict[Path, float]:
    return {p: p.stat().st_mtime for p in list_models(settings.GENERATED_DIR)}


# --- tools -----------------------------------------------------------------

async def t_find_parts(ctx: ToolContext, query: str, limit: int = 15) -> ToolResult:
    rows = ldraw.find_parts(query, limit=max(1, min(limit, 50)))
    if not rows:
        return ToolResult(f"No parts match {query!r}. Try fewer or more general words (e.g. 'plate 2 x 4', 'wheel', 'slope 45').")
    return ToolResult("\n".join(f'{r["id"]}\t{r["description"]}' for r in rows))


async def t_search_reference_models(ctx: ToolContext, query: str, limit: int = 8) -> ToolResult:
    rows = ldraw.search_reference_models(query, limit=max(1, min(limit, 25)))
    if not rows:
        return ToolResult(f"No reference models match {query!r}.")
    return ToolResult(json.dumps(rows, indent=1))


async def t_read_reference_model(ctx: ToolContext, file: str, submodel: str | None = None,
                                 max_lines: int = 250) -> ToolResult:
    try:
        text = ldraw.read_reference_model(file, submodel, max_lines=max(20, min(max_lines, 1500)))
    except FileNotFoundError as exc:
        raise ToolError(str(exc)) from None
    return ToolResult(text)


async def t_save_model(ctx: ToolContext, name: str, content: str, description: str | None = None) -> ToolResult:
    slug = _slug(name)
    settings.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    version = _next_version(slug)
    path = settings.GENERATED_DIR / f"{slug}-v{version}.mpd"

    checked = ldraw.validate_model(content, main_name=f"{slug}.ldr", description=description or name)
    path.write_text(checked.content)
    sandbox.give_to_agent(path)
    ref, render_error = await publish(ctx, path, name, checked.warnings)

    report: dict[str, Any] = {
        "saved": str(path),
        "version": version,
        "description": checked.title,
        "part_lines": checked.part_count,
        "parts": bom_part_count(bom_path_for(path)) if bom_path_for(path).exists() else "unknown (no BOM)",
        "bom": str(bom_path_for(path)),
        "submodels": checked.submodels,
        "warnings": ref["warnings"] or "none",
    }
    png = snapshot_path_for(path)
    if render_error:
        report["render_error"] = render_error
    else:
        report["snapshot"] = str(png)
    return ToolResult(json.dumps(report, indent=1), models=[ref], images=[png] if png.exists() else [])


async def t_render_model(ctx: ToolContext, path: str, latitude: float = 30, longitude: float = 40,
                         width: int = 1024, height: int = 768, submodel: str | None = None,
                         step: int | None = None) -> ToolResult:
    model = resolve_path(ctx, path)
    if not model.is_file():
        raise ToolError(f"{path} does not exist")
    suffix = f"{int(latitude)}_{int(longitude)}" + (f"-step{step}" if step else "") + (f"-{_slug(submodel)}" if submodel else "")
    png = ctx.chat_dir / "renders" / f"{model.stem}-{suffix}.png"
    try:
        await render.render(model, png, width=max(64, min(width, 2048)), height=max(64, min(height, 2048)),
                            camera_angles=(latitude, longitude), submodel=submodel, step=step)
    except Exception as exc:  # noqa: BLE001
        raise ToolError(f"render failed: {render.describe_error(exc)}") from None
    return ToolResult(f"Rendered {model} -> {png} (shown to the user)", images=[png])


async def _run_and_collect(ctx: ToolContext, argv: list[str], timeout: int) -> ToolResult:
    before = _collection_state()
    result = await sandbox.run(argv, ctx.work_dir, timeout=max(1, min(timeout, 300)))
    text = result.as_text()
    models, images = [], []
    for path, mtime in sorted(_collection_state().items()):
        if before.get(path) == mtime:
            continue
        checked = ldraw.validate_model(path.read_text(errors="replace"), main_name=path.name)
        ref, render_error = await publish(ctx, path, path.stem, checked.warnings)
        models.append(ref)
        png = snapshot_path_for(path)
        if png.exists() and not render_error:
            images.append(png)
        text += f"\n[published {path}: {checked.part_count} parts"
        text += f", snapshot failed: {render_error}]" if render_error else f", snapshot {png}]"
        if checked.warnings:
            text += "\n  warnings: " + "; ".join(checked.warnings[:10])
    return ToolResult(text, models=models, images=images)


async def t_run_python(ctx: ToolContext, code: str, timeout: int = 60) -> ToolResult:
    scripts = ctx.work_dir / ".scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    script = scripts / f"run-{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}.py"
    script.write_text(code)
    return await _run_and_collect(ctx, ["python3", str(script)], timeout)


async def t_run_shell(ctx: ToolContext, command: str, timeout: int = 60) -> ToolResult:
    return await _run_and_collect(ctx, ["bash", "-c", command], timeout)


async def t_list_files(ctx: ToolContext, path: str = "") -> ToolResult:
    folder = resolve_path(ctx, path) if path else ctx.work_dir
    if not folder.is_dir():
        raise ToolError(f"{path or folder} is not a folder")
    entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    lines = [f"{p.name}/" if p.is_dir() else f"{p.name}\t{p.stat().st_size} bytes" for p in entries[:500]]
    if len(entries) > 500:
        lines.append(f"... and {len(entries) - 500} more")
    return ToolResult(f"{folder}:\n" + ("\n".join(lines) or "(empty)"))


async def t_read_file(ctx: ToolContext, path: str, max_chars: int = 40_000) -> ToolResult:
    file = resolve_path(ctx, path)
    if not file.is_file():
        raise ToolError(f"{path} is not a file")
    data = file.read_bytes()
    if b"\0" in data[:4096]:
        raise ToolError(f"{path} is a binary file ({len(data)} bytes)")
    text = data.decode(errors="replace")
    limit = max(1000, min(max_chars, 200_000))
    if len(text) > limit:
        text = text[:limit] + f"\n... [truncated: {len(text)} characters total]"
    return ToolResult(text)


async def t_write_file(ctx: ToolContext, path: str, content: str, append: bool = False) -> ToolResult:
    file = resolve_path(ctx, path, write=True)
    if len(content.encode()) > MAX_WRITE_BYTES:
        raise ToolError(f"content is larger than {MAX_WRITE_BYTES} bytes")
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a" if append else "w", encoding="utf-8") as fh:
        fh.write(content)
    for owned in [file, *file.parents]:            # the agent's own scripts must be able to edit them
        if owned == ctx.work_dir or ctx.work_dir not in owned.parents:
            break
        sandbox.give_to_agent(owned)
    return ToolResult(f"{'Appended to' if append else 'Wrote'} {file} ({file.stat().st_size} bytes)")


# --- registry --------------------------------------------------------------

def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }}


TOOLS: dict[str, tuple[dict, Callable[..., Awaitable[ToolResult]]]] = {
    "find_parts": (_fn(
        "find_parts",
        "Search the official LDraw parts library by description or part number. "
        "Returns part ids (e.g. 3001.dat) with descriptions. Use it to find real part ids before writing a model.",
        {"query": {"type": "string", "description": "e.g. 'brick 2 x 4', 'plate 1 x 2', 'wheel', '3001'"},
         "limit": {"type": "integer", "description": "max results (default 15)"}},
        ["query"]), t_find_parts),
    "search_reference_models": (_fn(
        "search_reference_models",
        "Search ~1800 real LEGO set models (annotated LDraw files) by what they depict. "
        "Returns file names with per-submodel descriptions; read one with read_reference_model to learn how real builds are put together.",
        {"query": {"type": "string", "description": "e.g. 'fire truck', 'small house with door'"},
         "limit": {"type": "integer"}},
        ["query"]), t_search_reference_models),
    "read_reference_model": (_fn(
        "read_reference_model",
        "Read the LDraw source of a reference model, optionally just one submodel (a '0 FILE' section).",
        {"file": {"type": "string", "description": "file name from search_reference_models, e.g. '8303-1.mpd'"},
         "submodel": {"type": "string", "description": "submodel name, e.g. '8303 - Demon Destroyer.ldr'"},
         "max_lines": {"type": "integer", "description": "default 250"}},
        ["file"]), t_read_reference_model),
    "save_model": (_fn(
        "save_model",
        "Publish a finished LDraw model (.mpd/.ldr text) to the model collection (/data/generated), validate it "
        "and render its snapshot. Each call creates a new version (name-v1.mpd, name-v2.mpd, ...). Returns "
        "validation warnings (unknown parts, bad colours) and the snapshot path. The user sees the snapshot in "
        "the chat and on the Models page, and can open it in 3D.",
        {"name": {"type": "string", "description": "short model name, e.g. 'red car'"},
         "content": {"type": "string", "description": "full LDraw file content"},
         "description": {"type": "string", "description": "one-line description, written as the model's title "
                         "line (line 2 of the .mpd) if the content doesn't have one; shown on the Models page"}},
        ["name", "content"]), t_save_model),
    "render_model": (_fn(
        "render_model",
        "Render any model file (in /data/generated, your work folder or /opt/models-annotated) from a chosen "
        "camera angle, e.g. to check the back or underside of a build. The image is shown in the chat.",
        {"path": {"type": "string"},
         "latitude": {"type": "number", "description": "degrees above the horizon (default 30)"},
         "longitude": {"type": "number", "description": "degrees around the model (default 40)"},
         "width": {"type": "integer"}, "height": {"type": "integer"},
         "submodel": {"type": "string"}, "step": {"type": "integer", "description": "render up to this build step"}},
        ["path"]), t_render_model),
    "run_python": (_fn(
        "run_python",
        "Run a Python 3 script with your work folder as the current directory. Useful for generating models "
        "programmatically. `from leocad_render import render_image` is available. Keep drafts in the work folder; "
        "a .mpd/.ldr/.dat the script writes (or changes) in /data/generated is published: snapshotted and shown "
        "to the user.",
        {"code": {"type": "string"}, "timeout": {"type": "integer", "description": "seconds, default 60, max 300"}},
        ["code"]), t_run_python),
    "run_shell": (_fn(
        "run_shell",
        "Run a bash command in your work folder. `leocad` is on PATH. Models written to /data/generated are "
        "published like with run_python.",
        {"command": {"type": "string"}, "timeout": {"type": "integer"}},
        ["command"]), t_run_shell),
    "list_files": (_fn(
        "list_files",
        "List a folder: your work folder (default), /data/generated, or /opt/models-annotated.",
        {"path": {"type": "string"}}, []), t_list_files),
    "read_file": (_fn(
        "read_file",
        "Read a text file from your work folder, /data/generated or /opt/models-annotated.",
        {"path": {"type": "string"}, "max_chars": {"type": "integer"}},
        ["path"]), t_read_file),
    "write_file": (_fn(
        "write_file",
        "Write (or append to) a text file in your work folder, e.g. NOTES.md with the plan and progress, or a "
        "draft model. Relative paths are relative to the work folder.",
        {"path": {"type": "string"}, "content": {"type": "string"},
         "append": {"type": "boolean", "description": "append instead of overwrite (default false)"}},
        ["path", "content"]), t_write_file),
}

TOOL_SCHEMAS = [schema for schema, _fn_ in TOOLS.values()]


async def dispatch(ctx: ToolContext, name: str, arguments: str | dict) -> ToolResult:
    if name not in TOOLS:
        return ToolResult(f"Error: unknown tool {name!r}. Available: {', '.join(TOOLS)}")
    try:
        args = json.loads(arguments or "{}") if isinstance(arguments, str) else dict(arguments or {})
    except json.JSONDecodeError as exc:
        return ToolResult(f"Error: tool arguments are not valid JSON ({exc}). Call {name} again with valid JSON.")
    _schema, fn = TOOLS[name]
    try:
        inspect.signature(fn).bind(ctx, **args)
    except TypeError as exc:
        return ToolResult(f"Error: bad arguments for {name}: {exc}")
    try:
        return await fn(ctx, **args)
    except ToolError as exc:
        return ToolResult(f"Error: {exc}")
    except Exception as exc:  # noqa: BLE001 - a failing tool must not end the turn
        return ToolResult(f"Error: {name} failed: {exc.__class__.__name__}: {exc}")
