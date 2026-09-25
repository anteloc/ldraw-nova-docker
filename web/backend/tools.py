"""Tools the agents can call. Schemas are OpenAI function-calling format,
which LiteLLM translates for every provider."""
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
from leocad_render import output_path_for
from paths import rel_to, safe_join
from store import Store

MODEL_SUFFIXES = (".ldr", ".mpd")


class ToolError(Exception):
    """An error message meant for the agent (it can fix its call and retry)."""


@dataclass
class ToolContext:
    chat_id: str
    store: Store
    emit: Callable[[str, dict], None]

    @property
    def workspace(self) -> Path:
        return settings.GENERATED_DIR / self.chat_id


@dataclass
class ToolResult:
    content: str                                             # what the LLM sees
    artifacts: list[dict] = field(default_factory=list)      # generated models (store rows)
    images: list[str] = field(default_factory=list)          # PNGs, relative to DATA_DIR


# --- helpers ---------------------------------------------------------------

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "model"


def _data_rel(path: Path) -> str:
    return rel_to(path, settings.DATA_DIR)


def resolve_path(ctx: ToolContext, path: str) -> Path:
    """Paths the agent may read: /data/..., the reference models, or anything
    relative to its own workspace."""
    path = (path or "").strip()
    roots = [settings.DATA_DIR, settings.REF_MODELS_DIR]
    if path.startswith("/"):
        for root in roots:
            if path == str(root) or path.startswith(str(root) + "/"):
                resolved = safe_join(root, path[len(str(root)):])
                break
        else:
            raise ToolError(f"{path} is outside {settings.DATA_DIR} and {settings.REF_MODELS_DIR}")
    else:
        resolved = safe_join(ctx.workspace, path)
    if resolved is None:
        raise ToolError(f"{path} escapes the allowed folders")
    return resolved


async def register_model(ctx: ToolContext, model_path: Path, name: str, warnings: list[str]) -> tuple[dict, str | None]:
    """Render a model file in the workspace and record it as a chat artifact."""
    png = output_path_for(model_path)
    render_error = None
    try:
        await render.render(model_path, png, width=1024, height=768)
    except Exception as exc:  # noqa: BLE001 - reported to the agent and the UI
        render_error = render.describe_error(exc)
    artifact = ctx.store.add_artifact(
        ctx.chat_id, name, _data_rel(model_path),
        None if render_error else _data_rel(png), warnings,
    )
    ctx.emit("model", artifact)
    return artifact, render_error


def _model_files(workspace: Path) -> dict[Path, float]:
    if not workspace.exists():
        return {}
    return {p: p.stat().st_mtime for p in workspace.rglob("*")
            if p.is_file() and p.suffix.lower() in MODEL_SUFFIXES}


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


async def t_save_model(ctx: ToolContext, name: str, content: str) -> ToolResult:
    slug = _slug(name)
    ctx.workspace.mkdir(parents=True, exist_ok=True)
    sandbox.give_to_agent(ctx.workspace)
    versions = [int(m.group(1)) for p in ctx.workspace.glob(f"{slug}-v*.mpd")
                if (m := re.fullmatch(rf"{re.escape(slug)}-v(\d+)\.mpd", p.name))]
    version = max(versions, default=0) + 1
    path = ctx.workspace / f"{slug}-v{version}.mpd"

    checked = ldraw.validate_model(content, main_name=f"{slug}.ldr")
    path.write_text(checked.content)
    sandbox.give_to_agent(path)
    artifact, render_error = await register_model(ctx, path, name, checked.warnings)

    report: dict[str, Any] = {
        "saved": str(path),
        "version": version,
        "parts": checked.part_count,
        "submodels": checked.submodels,
        "warnings": checked.warnings or "none",
    }
    if render_error:
        report["render_error"] = render_error
    else:
        report["render"] = str(settings.DATA_DIR / artifact["image_path"])
    images = [artifact["image_path"]] if artifact["image_path"] else []
    return ToolResult(json.dumps(report, indent=1), artifacts=[artifact], images=images)


async def t_render_model(ctx: ToolContext, path: str, latitude: float = 30, longitude: float = 40,
                         width: int = 1024, height: int = 768, submodel: str | None = None,
                         step: int | None = None) -> ToolResult:
    model = resolve_path(ctx, path)
    if not model.is_file():
        raise ToolError(f"{path} does not exist")
    suffix = f"{int(latitude)}_{int(longitude)}" + (f"-step{step}" if step else "") + (f"-{_slug(submodel)}" if submodel else "")
    png = settings.OUTPUT_DIR / "generated" / ctx.chat_id / "renders" / f"{model.stem}-{suffix}.png"
    try:
        await render.render(model, png, width=max(64, min(width, 2048)), height=max(64, min(height, 2048)),
                            camera_angles=(latitude, longitude), submodel=submodel, step=step)
    except Exception as exc:  # noqa: BLE001
        raise ToolError(f"render failed: {render.describe_error(exc)}") from None
    return ToolResult(f"Rendered {model} -> {png}", images=[_data_rel(png)])


async def _run_and_collect(ctx: ToolContext, argv: list[str], timeout: int) -> ToolResult:
    before = _model_files(ctx.workspace)
    result = await sandbox.run(argv, ctx.workspace, timeout=max(1, min(timeout, 300)))
    text = result.as_text()
    artifacts, images = [], []
    for path, mtime in sorted(_model_files(ctx.workspace).items()):
        if before.get(path) == mtime:
            continue
        checked = ldraw.validate_model(path.read_text(errors="replace"), main_name=path.name)
        artifact, render_error = await register_model(ctx, path, path.stem, checked.warnings)
        artifacts.append(artifact)
        if artifact["image_path"]:
            images.append(artifact["image_path"])
        text += f"\n[new/changed model {path}: {checked.part_count} parts"
        text += f", render failed: {render_error}]" if render_error else f", rendered to {settings.DATA_DIR / artifact['image_path']}]"
        if checked.warnings:
            text += "\n  warnings: " + "; ".join(checked.warnings[:10])
    return ToolResult(text, artifacts=artifacts, images=images)


async def t_run_python(ctx: ToolContext, code: str, timeout: int = 60) -> ToolResult:
    scripts = ctx.workspace / ".scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    script = scripts / f"run-{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}.py"
    script.write_text(code)
    return await _run_and_collect(ctx, ["python3", str(script)], timeout)


async def t_run_shell(ctx: ToolContext, command: str, timeout: int = 60) -> ToolResult:
    return await _run_and_collect(ctx, ["bash", "-c", command], timeout)


async def t_list_files(ctx: ToolContext, path: str = "") -> ToolResult:
    folder = resolve_path(ctx, path) if path else ctx.workspace
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
        "Save an LDraw model (.mpd/.ldr text) to the chat's workspace, validate it and render a screenshot. "
        "Each call creates a new version (name-v1.mpd, name-v2.mpd, ...). Returns validation warnings "
        "(unknown parts, bad colours) and the render path. The user sees the screenshot and can open it in 3D.",
        {"name": {"type": "string", "description": "short model name, e.g. 'red car'"},
         "content": {"type": "string", "description": "full LDraw file content"}},
        ["name", "content"]), t_save_model),
    "render_model": (_fn(
        "render_model",
        "Render any model file (in /data, /opt/models-annotated or the workspace) from a chosen camera angle, "
        "e.g. to check the back or underside of a build.",
        {"path": {"type": "string"},
         "latitude": {"type": "number", "description": "degrees above the horizon (default 30)"},
         "longitude": {"type": "number", "description": "degrees around the model (default 40)"},
         "width": {"type": "integer"}, "height": {"type": "integer"},
         "submodel": {"type": "string"}, "step": {"type": "integer", "description": "render up to this build step"}},
        ["path"]), t_render_model),
    "run_python": (_fn(
        "run_python",
        "Run a Python 3 script in the chat's workspace (current directory). Useful for generating models "
        "programmatically. `from leocad_render import render_image` is available. Any .ldr/.mpd file the script "
        "creates or changes in the workspace is rendered and shown to the user automatically.",
        {"code": {"type": "string"}, "timeout": {"type": "integer", "description": "seconds, default 60, max 300"}},
        ["code"]), t_run_python),
    "run_shell": (_fn(
        "run_shell",
        "Run a bash command in the chat's workspace. `leocad` is on PATH. New/changed .ldr/.mpd files are rendered automatically.",
        {"command": {"type": "string"}, "timeout": {"type": "integer"}},
        ["command"]), t_run_shell),
    "list_files": (_fn(
        "list_files",
        "List a folder: the workspace (default), anything under /data, or /opt/models-annotated.",
        {"path": {"type": "string"}}, []), t_list_files),
    "read_file": (_fn(
        "read_file",
        "Read a text file from the workspace, /data or /opt/models-annotated.",
        {"path": {"type": "string"}, "max_chars": {"type": "integer"}},
        ["path"]), t_read_file),
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
