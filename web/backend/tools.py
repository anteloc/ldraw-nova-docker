"""Tools the agents can call. Schemas are OpenAI function-calling format,
which LiteLLM translates for every provider.

Where things go:
  /data/generated/        finished models (flat) + their .png snapshots: the My Models page
  /data/output/<chat>/    the chat's work folder: scripts' cwd, notes, plans, scratch files
  /data/chats/<chat>/renders/   extra renders shown in the chat
"""
from __future__ import annotations

import inspect
import hashlib
import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote

import sandbox
import settings
import toolkit
import environment_config
from leocad_render import bom_path_for, list_models, snapshot_path_for
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
    """Paths the agent may use. Reading: the model collection and its own work
    folder. Writing (write_file): only its work folder.
    Relative paths are relative to the work folder."""
    path = (path or "").strip()
    roots = [ctx.work_dir] if write else [ctx.work_dir, settings.GENERATED_DIR, settings.TOOLKIT_DIR]
    if any(p.startswith(".") for p in Path(path).parts if p not in (".", "..")):
        raise ToolError("Hidden configuration and runtime files are not accessible through file tools")
    if path.startswith("output/") or path == "output":
        path = str(ctx.work_dir / path.removeprefix("output").lstrip("/"))
    elif not write and not path.startswith("/") and (settings.TOOLKIT_DIR / path).exists():
        path = str(settings.TOOLKIT_DIR / path)
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


async def _run_and_collect(ctx: ToolContext, argv: list[str], timeout: int) -> ToolResult:
    result = await run_command(ctx, argv, timeout)
    return ToolResult(result.as_text())


async def run_command(ctx: ToolContext, argv: list[str], timeout: int) -> sandbox.RunResult:
    env = toolkit.environment()
    key = environment_config.snapshot().get("TYPESAFE_API_KEY", "")
    if key:
        env["TYPESAFE_API_KEY"] = key
    return await sandbox.run(argv, toolkit.workspace(ctx.store, ctx.chat_id), timeout=max(1, min(timeout, 1800)),
                             env_extra=env, secrets=(key,),
                             on_output=lambda channel, text: ctx.emit("tool_output", {"channel": channel, "delta": text}))


async def t_run_python(ctx: ToolContext, code: str, timeout: int = 60) -> ToolResult:
    scripts = ctx.work_dir / "generators"
    scripts.mkdir(parents=True, exist_ok=True)
    script = scripts / f"run-{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}.py"
    script.write_text(code)
    sandbox.give_to_agent(scripts)
    sandbox.give_to_agent(script)
    result = await _run_and_collect(ctx, ["python3", str(script)], timeout)
    result.content += f"\nSaved generator: {artifact_url(ctx, script)}"
    return result


async def t_run_shell(ctx: ToolContext, command: str, timeout: int = 60) -> ToolResult:
    return await _run_and_collect(ctx, ["bash", "-o", "pipefail", "-c", command], timeout)


async def t_run_toolkit(ctx: ToolContext, arguments: list[str], timeout: int = 300) -> ToolResult:
    if not arguments or not all(isinstance(a, str) and "\0" not in a for a in arguments):
        raise ToolError("arguments must be a nonempty array of CLI argument strings")
    return await _run_and_collect(ctx, ["./ldraw-agent", *arguments], timeout)


async def t_report_progress(ctx: ToolContext, summary: str) -> ToolResult:
    summary = summary.strip()[:2000]
    ctx.emit("progress", {"summary": summary})
    return ToolResult(summary)


async def t_view_image(ctx: ToolContext, path: str) -> ToolResult:
    source = resolve_path(ctx, path)
    if not source.is_file() or source.stat().st_size > 16 * 1024 * 1024:
        raise ToolError("Choose an existing PNG smaller than 16 MB")
    data = source.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ToolError("view_image accepts PNG renders")
    target = ctx.chat_dir / "renders" / (hashlib.sha256(data).hexdigest()[:24] + ".png")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return ToolResult(f"Opened {path} for visual review.", images=[target])


def artifact_url(ctx: ToolContext, path: Path) -> str:
    return f"/api/chats/{ctx.chat_id}/artifacts/" + quote(path.relative_to(ctx.work_dir).as_posix())


async def t_publish_model(ctx: ToolContext, path: str, name: str | None = None) -> ToolResult:
    source = resolve_path(ctx, path, write=True)
    if not source.is_file() or source.suffix.lower() not in {".mpd", ".ldr"}:
        raise ToolError("Publish a self-contained .mpd or .ldr from this chat's output folder")
    if source.stat().st_size > 32 * 1024 * 1024:
        raise ToolError("Model exceeds the 32 MB publication limit")
    import uuid
    review = ctx.work_dir / "publication" / uuid.uuid4().hex[:12]
    review.mkdir(parents=True)
    sandbox.give_to_agent(review.parent)
    sandbox.give_to_agent(review)
    # Validate and render the same captured revision even if another tool or
    # the user edits the working source while publication is running.
    source_bytes = source.read_bytes()
    revision = review / "model.mpd"
    revision.write_bytes(source_bytes)
    report = review / "validation.json"
    ctx.emit("progress", {"summary": "Checking the model with LDraw Astra before publication."})
    validation = await run_command(ctx, ["./ldraw-agent", "validate", str(revision), "--geometry",
                                         "--detail", "summary", "--report", str(report)], 1800)
    if validation.exit_code not in (0, 1) or not report.is_file():
        return ToolResult("Error: toolkit validation could not finish; model was not published.\n" + validation.as_text())
    warnings = ["Physical buildability is not proven; read the validation and visual review reports."]
    if validation.exit_code == 1:
        warnings.append("Toolkit validation failed. This revision is for inspection and needs repair.")
    slug = _slug(name or source.stem)
    settings.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    # Reserve synchronously before the next await, including concurrent chats.
    target = settings.GENERATED_DIR / f"{slug}-v{_next_version(slug)}.mpd"
    target.write_bytes(source_bytes)
    ctx.emit("progress", {"summary": "Rendering the published model and exporting its parts list."})
    rendered = await run_command(ctx, ["./ldraw-agent", "render", str(target), "--outdir", str(review),
                                      "--views", "home"], 600)
    image, bom = review / "home.png", review / "leocad-bom.csv"
    if rendered.exit_code == 0 and image.exists() and bom.exists():
        shutil.copyfile(image, snapshot_path_for(target))
        shutil.copyfile(bom, bom_path_for(target))
    else:
        warnings.append("Preview/BOM rendering failed; the model can still be opened in 3D.")
    ref = ctx.store.add_model(ctx.chat_id, name or source.stem, target, warnings)
    ctx.emit("model", {"id": ref["id"], "name": ref["name"]})
    result = {"model_url": "/files/generated/" + quote(target.name), "source": artifact_url(ctx, source),
              "sha256": hashlib.sha256(source_bytes).hexdigest(),
              "validation": artifact_url(ctx, report), "checks_passed": validation.exit_code == 0,
              "validation_path": str(report),
              "physical_validity": "not_proven", "warnings": warnings,
              "note": "Open the preview with view_image and complete visual review and compare-bom before final delivery."}
    if image.exists():
        result["preview"] = artifact_url(ctx, image)
        result["preview_path"] = str(image)
    if bom.exists():
        result["bom"] = artifact_url(ctx, bom)
        result["bom_path"] = str(bom)
    return ToolResult(json.dumps(result, indent=2), models=[ref])


async def t_list_files(ctx: ToolContext, path: str = "") -> ToolResult:
    folder = resolve_path(ctx, path) if path else toolkit.workspace(ctx.store, ctx.chat_id)
    if not folder.is_dir():
        raise ToolError(f"{path or folder} is not a folder")
    entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    lines = [f"{p.name}/" if p.is_dir() else f"{p.name}\t{p.stat().st_size} bytes" for p in entries[:500]]
    if len(entries) > 500:
        lines.append(f"... and {len(entries) - 500} more")
    return ToolResult(f"{folder}:\n" + ("\n".join(lines) or "(empty)"))


async def t_read_file(ctx: ToolContext, path: str, max_chars: int = 40_000, offset: int = 0) -> ToolResult:
    file = resolve_path(ctx, path)
    if not file.is_file():
        raise ToolError(f"{path} is not a file")
    if file.stat().st_size > 8 * 1024 * 1024:
        raise ToolError("File exceeds 8 MB; inspect it with a bounded toolkit or shell command")
    data = file.read_bytes()
    if b"\0" in data[:4096]:
        raise ToolError(f"{path} is a binary file ({len(data)} bytes)")
    text = data.decode(errors="replace")
    limit = max(1000, min(max_chars, 200_000))
    total = len(text)
    offset = max(0, offset)
    text = text[offset:offset + limit]
    if offset + limit < total:
        text += f"\n... [truncated: {total} characters total; continue at offset {offset + limit}]"
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
    "run_toolkit": (_fn("run_toolkit",
        "Run the standalone LDraw Astra CLI. All commands are available: doctor, spec, discover, catalog, "
        "study, extract, examples, build, validate, inspect, render, compare-bom, manual, vehicle, spaceship, "
        "technic, mechanism and more. Read instructions.md and relevant docs first. Output goes under output/. "
        "Arguments are an array, without shell quoting or the executable. Use --help to inspect subcommands.",
        {"arguments": {"type": "array", "items": {"type": "string"}},
         "timeout": {"type": "integer", "description": "Seconds, default 300, maximum 1800"}},
        ["arguments"]), t_run_toolkit),
    "publish_model": (_fn("publish_model",
        "Publish an output MPD revision as an interactive model card in this chat and the Models collection. "
        "Preserves source bytes, runs toolkit geometry validation, renders a snapshot and BOM. Failed checks "
        "are flagged for repair. Use after generating a model and again after final visual review. "
        "Return links to plans, generator, manifests, reports and reviews alongside the card.",
        {"path": {"type": "string"}, "name": {"type": "string"}}, ["path"]), t_publish_model),
    "view_image": (_fn("view_image", "Open a PNG from the toolkit examples or output for actual visual review. "
        "The image is shown to you and the user. Use on rendered views before recording a visual review.",
        {"path": {"type": "string"}}, ["path"]), t_view_image),
    "report_progress": (_fn("report_progress", "Show a concise progress update: current phase, design decisions, "
        "completed checks, remaining work. Use throughout substantial builds, without private internal reasoning.",
        {"summary": {"type": "string"}}, ["summary"]), t_report_progress),
    "run_python": (_fn("run_python", "Run Python with the LDraw Astra virtualenv (pyldraw3, numpy, jsonschema). "
        "Working directory has the toolkit repository layout. Use its builder/serializer; write under output/. "
        "Code is saved for reproducibility. Call publish_model for user-visible model cards.",
        {"code": {"type": "string"}, "timeout": {"type": "integer", "description": "Seconds, default 60, max 1800"}},
        ["code"]), t_run_python),
    "run_shell": (_fn("run_shell", "Run bash in the toolkit workspace, with pipefail and live output. "
        "./ldraw-agent, ./check-model.sh, ./prepare-glb.sh and global CLIs are available. "
        "TYPESAFE_API_KEY comes from Settings; never print it. Write under output/. "
        "Call publish_model to show a generated model in the chat.",
        {"command": {"type": "string"}, "timeout": {"type": "integer", "description": "Seconds, default 60, max 1800"}},
        ["command"]), t_run_shell),
    "list_files": (_fn("list_files", "List toolkit resources or this chat's output/ (default: repository root).",
        {"path": {"type": "string"}}, []), t_list_files),
    "read_file": (_fn("read_file", "Read toolkit instructions, documentation, examples or your output files. "
        "Use offset to continue a truncated file. Query PDFs through run_toolkit spec.",
        {"path": {"type": "string"}, "max_chars": {"type": "integer"}, "offset": {"type": "integer"}},
        ["path"]), t_read_file),
    "write_file": (_fn("write_file", "Write a plan, generator, notes or report in output/. "
        "Bare relative paths also resolve under output/. Shared toolkit resources cannot be changed.",
        {"path": {"type": "string"}, "content": {"type": "string"}, "append": {"type": "boolean"}},
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
