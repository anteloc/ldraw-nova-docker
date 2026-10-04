"""Provider-agnostic agent loop on top of LiteLLM.

A turn runs as a background asyncio task per chat (so reloading the page
doesn't kill it). The chat's files (store.py) are the source of truth; live
events only carry what's in flight (streaming text, running tools) plus
"saved" pings telling the UI to refetch.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

import litellm

import llm_config
import browser_auth
import inference
import model_catalog
import settings
import toolkit
from store import ChatStore
from tools import SCULPTURE_SCHEMAS, TOOL_SCHEMAS, ToolContext, ToolResult, dispatch

log = logging.getLogger("agent")

litellm.drop_params = False           # unsupported settings must fail visibly
litellm.suppress_debug_info = True

MAX_STEPS = 150
KEEP_IMAGE_MESSAGES = 2               # only the newest renders are re-sent to vision models
WORK_LISTING_LIMIT = 60               # files of the work folder listed in the system prompt


@dataclass
class Run:
    chat_id: str
    task: Optional[asyncio.Task] = None
    draft: str = ""
    tools_running: dict[str, dict] = field(default_factory=dict)
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    options: dict = field(default_factory=dict)
    approvals: dict[str, tuple[dict, asyncio.Future]] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    last_event_at: float = field(default_factory=time.time)
    phase: str = "Preparing the build workspace"
    sculpture: dict = field(default_factory=dict)

    def emit(self, event: str, data: dict) -> None:
        self.last_event_at = time.time()
        if event == "progress":
            self.phase = data["summary"]
        elif event == "tool_start":
            data.setdefault("started_at", time.time())
            self.phase = {
                "run_toolkit": "Running LDraw Nova",
                "run_python": "Running the model generator",
                "run_shell": "Running a build command",
                "publish_model": "Checking and publishing the model",
                "view_image": "Reviewing a rendered image",
                "read_file": "Reading build instructions or reports",
                "write_file": "Saving build files",
                "list_files": "Inspecting available files",
            }.get(data.get("name"), self.phase)
        elif event == "tool_output":
            tool = self.tools_running.get(data.get("id"))
            if tool is not None:
                tool["output"] = (tool.get("output", "") + data.get("delta", ""))[-12000:]
        for queue in list(self.subscribers):
            if queue.full():
                # Disconnect slow consumers; their reconnection receives a fresh
                # state snapshot rather than an unbounded backlog of command logs.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(("reconnect", {}))
                self.subscribers.discard(queue)
            else:
                queue.put_nowait((event, dict(data)))

    def activity(self) -> dict:
        return {"started_at": self.started_at, "last_event_at": self.last_event_at, "phase": self.phase}


_runs: dict[str, Run] = {}


def is_running(chat_id: str) -> bool:
    run = _runs.get(chat_id)
    return bool(run and run.task and not run.task.done())


def work_listing(work_dir: Path) -> str:
    """What's in the work folder right now, for the system prompt: whoever
    continues the chat (possibly another model) sees what earlier turns left."""
    if not work_dir.is_dir():
        return "(empty)"
    files = sorted(p for p in work_dir.rglob("*") if p.is_file() and ".scripts" not in p.relative_to(work_dir).parts)
    scripts = sum(1 for _ in (work_dir / ".scripts").glob("*")) if (work_dir / ".scripts").is_dir() else 0
    lines = [f"- {p.relative_to(work_dir)} ({p.stat().st_size} bytes)" for p in files[:WORK_LISTING_LIMIT]]
    if len(files) > WORK_LISTING_LIMIT:
        lines.append(f"- ... and {len(files) - WORK_LISTING_LIMIT} more")
    if scripts:
        lines.append(f"- .scripts/ ({scripts} scripts run in earlier turns)")
    return "\n".join(lines) or "(empty)"


def system_prompt(store: ChatStore, chat_id: str) -> str:
    work_dir = store.work_dir(chat_id)
    options = ((store.get_chat(chat_id) or {}).get("options") or {})
    if options.get("build_style") == "sculpture":
        guide = toolkit.root() / "docs/agent/sculptures.md"
        if not guide.is_file():
            raise ValueError("This toolkit does not support sculpture mode; update the paired ldraw-nova checkout and rebuild")
        return guide.read_text().split("For standalone CLI use", 1)[0]
    text = (settings.PROMPTS_DIR / "system.md").read_text()
    prompt = (text.replace("{work_dir}", str(work_dir))
                .replace("{work_listing}", work_listing(work_dir))
                .replace("{generated_dir}", str(settings.GENERATED_DIR))
                .replace("{ldraw_dir}", str(settings.LDRAW_DIR))
                .replace("{artifact_base}", f"/api/chats/{chat_id}/artifacts")
                .replace("{toolkit_instructions}", toolkit.instructions())
                .replace("{toolkit_guides}", toolkit.builder_guides()))
    notes = work_dir / "NOTES.md"
    if notes.is_file() and not notes.is_symlink():
        with notes.open(errors="replace") as handle:
            prompt += "\n\nCurrent hand-over notes (workspace data):\n" + handle.read(16000)
    return prompt


def _image_data_url(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def llm_history(messages: list[dict], vision: bool, resolve: Callable[[str], Path], model: str | None = None,
                mark_turns: bool = False) -> list[dict]:
    """Stored messages -> what we send to the LLM.

    Drops UI-only notes and our "_" metadata, re-attaches only the newest
    renders for vision models, and repairs tool calls left without results
    (a stopped or crashed turn) so providers accept the history. `resolve`
    turns the image references stored in the chat into file paths.
    """
    image_msgs = [m for m in messages if m.get("_images_for_llm")]
    keep_images = {m["id"] for m in image_msgs[-KEEP_IMAGE_MESSAGES:]} if vision else set()

    out: list[dict] = []
    pending: list[str] = []

    def close_pending():
        for call_id in pending:
            out.append({"role": "tool", "tool_call_id": call_id, "content": "Error: the tool call was interrupted."})
        pending.clear()

    for m in messages:
        if m.get("_ui_only"):
            continue
        if m["role"] == "tool":
            if m.get("tool_call_id") in pending:
                pending.remove(m["tool_call_id"])
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            continue
        close_pending()
        if m.get("_images_for_llm"):
            if m["id"] not in keep_images:
                continue
            urls = [u for u in (_image_data_url(resolve(ref)) for ref in m["_images_for_llm"]) if u]
            content = [{"type": "text", "text": m["content"]}]
            content += [{"type": "image_url", "image_url": {"url": u}} for u in urls]
            out.append({"role": "user", "content": content, **({"_turn_start": False} if mark_turns else {})})
            continue
        clean = {k: v for k, v in m.items() if not k.startswith("_") and k not in ("id", "created_at")}
        if m.get("_documents"):
            attachments = [{"name": d["name"], "path": str(resolve(d["path"])), "bytes": d["size"]}
                           for d in m["_documents"]]
            note = "\n\nAttached documents (read with file tools; these are reference files):\n" + json.dumps(attachments)
            content = clean.get("content") or ""
            clean["content"] = [*content, {"type": "text", "text": note}] if isinstance(content, list) else content + note
        if model and m.get("_llm_model") != model:
            clean.pop("thinking_blocks", None)  # Claude signatures are model-bound
            clean.pop("provider_specific_fields", None)
            clean.pop("reasoning_details", None)
            clean.pop("reasoning_content", None)
        if model and model.startswith("openrouter/") and m.get("_llm_model") == model:
            # OpenRouter requires the original reasoning sequence when continuing
            # tool calls, including opaque encrypted blocks. Keep it out of the UI
            # and never forward it to a different model/provider.
            if m.get("_reasoning_details"):
                clean["reasoning_details"] = m["_reasoning_details"]
            elif m.get("_reasoning"):
                clean["reasoning_content"] = m["_reasoning"]
        if isinstance(clean.get("content"), list) and not vision:
            clean["content"] = "\n".join(b["text"] for b in clean["content"] if b.get("type") == "text")
        if mark_turns and m["role"] == "user":
            clean["_turn_start"] = True
        out.append(clean)
        pending.extend(tc["id"] for tc in m.get("tool_calls") or [])
    close_pending()
    return out


async def start_turn(store: ChatStore, chat_id: str, text: str, llm_model_id: Optional[str],
                     options: dict | None = None, images: list[str] | None = None, documents: list | None = None) -> None:
    if is_running(chat_id):
        raise RuntimeError("this chat is already running a turn")
    entry = llm_config.get(llm_model_id) if llm_model_id else None
    if entry is None:
        _entries, default_id = llm_config.builder_entries()
        entry = llm_config.get(default_id) if default_id else None
    if entry is None:
        raise ValueError("no LLM model configured — add one in Settings")
    if (not model_catalog.builder_supported(entry["litellm_params"]["model"])
            or any(value is False for value in llm_config.capabilities(entry).values())):
        raise ValueError("Choose a model with tool calling and image input support in Settings")

    options = model_catalog.validate_options(entry, options)
    if images and llm_config.capabilities(entry)["vision"] is not True:
        raise ValueError("Select a model with image input support")
    if entry.get("auth_mode") == "browser":
        provider = "anthropic" if entry["litellm_params"]["model"].startswith("anthropic/") else "openai"
        if not await browser_auth.connected(provider):
            raise ValueError("Sign in to the provider in Settings first")
    # A concurrent request may have started while browser auth status was checked.
    if is_running(chat_id):
        raise RuntimeError("this chat is already running a turn")

    chat = store.get_chat(chat_id)
    if chat["title"] == "New chat":
        title = " ".join(text.split())
        store.update_chat(chat_id, title=title[:60] + ("…" if len(title) > 60 else ""))
    store.update_chat(chat_id, llm_model_id=entry["id"], options=options)
    content = ([{"type": "text", "text": text}, *[{"type": "image_url", "image_url": {"url": u}} for u in images]]
               if images else text)
    from attachments import save_documents
    attached = save_documents(store, chat_id, documents or [])
    store.add_message(chat_id, {"role": "user", "content": content, **({"_documents": attached} if attached else {})})

    run = _runs.get(chat_id) or Run(chat_id)
    _runs[chat_id] = run
    run.draft, run.tools_running = "", {}
    run.options, run.approvals, run.sculpture = options, {}, {}
    run.started_at = run.last_event_at = time.time()
    run.phase = "Preparing the build workspace"
    run.task = asyncio.create_task(_run_turn(store, run, entry))


async def cancel(chat_id: str) -> bool:
    run = _runs.get(chat_id)
    if not run or not run.task or run.task.done():
        return False
    run.task.cancel()
    try:
        await run.task
    except asyncio.CancelledError:
        pass
    return True


async def subscribe(chat_id: str) -> AsyncIterator[tuple[str, dict]]:
    run = _runs.get(chat_id)
    if run is None or not is_running(chat_id):
        yield "snapshot", {"running": False, "draft": "", "tools": []}
        return
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    run.subscribers.add(queue)
    try:
        yield "snapshot", {"running": True, "draft": run.draft, "tools": list(run.tools_running.values()),
                           "approvals": [a for a, _ in run.approvals.values()], "activity": run.activity()}
        while True:
            try:
                event, data = await asyncio.wait_for(queue.get(), timeout=5)
            except asyncio.TimeoutError:
                yield "activity", run.activity()
                continue
            yield event, data
            if event in {"done", "reconnect"}:
                return
    finally:
        run.subscribers.discard(queue)


async def _run_turn(store: ChatStore, run: Run, entry: dict) -> None:
    chat_id = run.chat_id
    caps = llm_config.capabilities(entry)
    vision = caps["vision"] is True
    use_tools = caps["tools"] is not False and run.options.get("mode") != "chat"
    ctx = ToolContext(chat_id=chat_id, store=store, emit=run.emit, sculpture=run.sculpture)

    def save(message: dict) -> int:
        msg_id = store.add_message(chat_id, message)
        run.emit("saved", {"message_id": msg_id})
        return msg_id

    try:
        if entry.get("auth_mode") == "browser" and entry["litellm_params"]["model"].startswith("anthropic/"):
            from claude_agent import run_claude
            await run_claude(store, run, entry, save, execute_tool, system_prompt(store, chat_id), use_tools)
            await finish_sculpture(run, ctx, save)
            return
        params = await inference.params_for(entry, run.options)
        for _step in range(step_limit(run.options)):
            prompt = system_prompt(store, chat_id) + mode_prompt(run.options)
            messages = [{"role": "system", "content": prompt},
                        *llm_history(store.messages(chat_id), vision, lambda ref: store.resolve(chat_id, ref), entry["litellm_params"]["model"], mark_turns=True)]
            budget = run.options.get("context_tokens") or model_catalog.profile(entry["litellm_params"]["model"])["context_window"]
            messages, removed = inference.bounded_history(messages, params["model"], budget)
            if removed:
                run.emit("context", {"removed": removed})
            kwargs = {"tools": available_tools(run.options)} if use_tools else {}
            run.emit("progress", {"summary": "Agent is reviewing the request and choosing the next step."})
            stream = await litellm.acompletion(**params, messages=messages, stream=True, num_retries=2, **kwargs)
            inference.preserve_openrouter_reasoning_chunks(stream, params["model"])

            run.draft = ""
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is not None and getattr(delta, "content", None):
                    run.draft += delta.content
                    run.emit("text", {"delta": delta.content})

            full = litellm.stream_chunk_builder(chunks, messages=messages)
            reply = full.choices[0].message
            tool_calls = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
                for tc in (reply.tool_calls or [])
            ]
            # null (not "") content next to tool calls: some providers reject empty text blocks.
            message: dict = {"role": "assistant", "content": reply.content or (None if tool_calls else "")}
            message["_llm_model"] = entry["litellm_params"]["model"]
            if tool_calls:
                message["tool_calls"] = tool_calls
            if getattr(reply, "thinking_blocks", None):          # must round-trip for Anthropic thinking
                message["thinking_blocks"] = reply.thinking_blocks
            if getattr(reply, "provider_specific_fields", None):
                message["provider_specific_fields"] = reply.provider_specific_fields
            if getattr(reply, "reasoning_content", None):
                message["_reasoning"] = reply.reasoning_content
            if message["_llm_model"].startswith("openrouter/"):
                # LiteLLM 1.102.1 retains delta.reasoning_details but loses them
                # in stream_chunk_builder. OpenRouter specifies concatenation in
                # received order; do not merge/reorder blocks by id or index.
                details = [detail for chunk in chunks if chunk.choices
                           for detail in (getattr(chunk.choices[0].delta, "reasoning_details", None) or [])]
                if details:
                    message["_reasoning_details"] = details
            if not message["content"] and not tool_calls:
                break                                              # nothing to save or do
            save(message)
            run.draft = ""
            if not tool_calls:
                break

            images: list[str] = []                             # relative to the chat folder
            for call in tool_calls:
                name = call["function"]["name"]
                run.tools_running[call["id"]] = {"id": call["id"], "name": name,
                                                 "arguments": call["function"]["arguments"]}
                run.emit("tool_start", run.tools_running[call["id"]])
                result = await execute_tool(run, ctx, call["id"], name, call["function"]["arguments"])
                run.tools_running.pop(call["id"], None)
                refs = [store.ref(chat_id, png) for png in result.images]
                save({"role": "tool", "tool_call_id": call["id"], "name": name, "content": result.content,
                      "_models": [m["id"] for m in result.models], "_images": refs})
                run.emit("tool_end", {"id": call["id"], "name": name})
                images += refs
            if images and vision:
                save({"role": "user", "content": "Renders produced by the tool calls above:",
                      "_images_for_llm": images, "_hidden": True})
            if run.sculpture.get("finished"):
                break
        else:
            if not sculpture_mode(run.options):
                save({"role": "assistant", "_ui_only": True, "_notice": True,
                      "content": f"Stopped after {MAX_STEPS} steps. Send a message to continue."})
        await finish_sculpture(run, ctx, save)
    except asyncio.CancelledError:
        if run.draft:
            save({"role": "assistant", "content": run.draft})
        save({"role": "assistant", "_ui_only": True, "_notice": True, "content": "Stopped."})
        raise
    except Exception as exc:  # noqa: BLE001 - provider/auth/network errors end the turn, not the chat
        log.warning("turn failed for chat %s: %s", chat_id, exc.__class__.__name__)
        message = str(exc) if isinstance(exc, ValueError) else f"{exc.__class__.__name__}: Provider request failed. Check login, model access and settings."
        save({"role": "assistant", "_ui_only": True, "_error": True, "content": message})
        run.emit("turn_error", {"message": message})   # not "error": EventSource reserves it
    finally:
        run.draft, run.tools_running = "", {}
        for _, future in run.approvals.values():
            if not future.done():
                future.cancel()
        run.approvals.clear()
        run.emit("done", {})


READ_TOOLS = {"list_files", "read_file", "view_image", "report_progress"}


def sculpture_mode(options: dict) -> bool:
    return (options.get("build_style") == "sculpture" and options.get("mode", "agent") == "agent"
            and options.get("permissions") != "read_only")


def step_limit(options: dict) -> int:
    return 6 if sculpture_mode(options) else MAX_STEPS


async def finish_sculpture(run: Run, ctx: ToolContext, save) -> None:
    """Keep a successful design when a bounded turn ends without explicit acceptance."""
    if not sculpture_mode(run.options) or run.sculpture.get("finished"):
        return
    if not run.sculpture.get("best"):
        raise ValueError("No successful voxel design was produced within the design-attempt limit")
    import uuid
    call_id = uuid.uuid4().hex
    save({"role": "assistant", "content": None, "tool_calls": [
        {"id": call_id, "type": "function", "function": {"name": "accept_design", "arguments": "{}"}}]})
    info = {"id": call_id, "name": "accept_design", "arguments": "{}"}
    run.tools_running[call_id] = info
    run.emit("tool_start", info)
    try:
        result = await execute_tool(run, ctx, call_id, "accept_design", "{}")
        save({"role": "tool", "tool_call_id": call_id, "name": "accept_design", "content": result.content,
              "_models": [m["id"] for m in result.models]})
        if result.models:
            info = json.loads(result.content)
            save({"role": "assistant", "content": f"Finished the sculpture: [{result.models[0]['name']}]({info['card_url']}). "
                  f"{info['sculpture']['brick_count']} rectangular bricks."})
    finally:
        run.tools_running.pop(call_id, None)
        run.emit("tool_end", {"id": call_id, "name": "accept_design"})


def mode_prompt(options: dict) -> str:
    if options.get("mode") == "plan":
        return "\nPLAN MODE: inspect with read-only tools and propose a plan. Do not execute commands or change files."
    if options.get("mode") == "chat":
        return "\nCHAT MODE: answer without using tools."
    return ""


def available_tools(options: dict) -> list[dict]:
    if options.get("mode") == "chat":
        return []
    if options.get("mode") == "plan" or options.get("permissions") == "read_only":
        return [t for t in TOOL_SCHEMAS if t["function"]["name"] in READ_TOOLS]
    return SCULPTURE_SCHEMAS if sculpture_mode(options) else TOOL_SCHEMAS


async def execute_tool(run: Run, ctx: ToolContext, call_id: str, name: str, arguments: str) -> ToolResult:
    allowed = {t["function"]["name"] for t in available_tools(run.options)}
    if name not in allowed:
        return ToolResult("Tool denied by the current mode or permissions.")
    if name not in READ_TOOLS and run.options.get("permissions", "ask") == "ask":
        # Independent approval IDs prevent replay between turns or duplicate provider call IDs.
        import uuid
        approval_id = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        info = {"id": approval_id, "call_id": call_id, "name": name, "arguments": arguments}
        run.approvals[approval_id] = (info, future)
        run.emit("approval", info)
        try:
            approved = await asyncio.wait_for(future, 600)
        except asyncio.TimeoutError:
            approved = False
        finally:
            run.approvals.pop(approval_id, None)
            run.emit("approval_resolved", {"id": approval_id})
        if not approved:
            return ToolResult("Tool denied by the user or approval timed out. Do not retry without a new user instruction.")
    scoped = replace(ctx, emit=lambda event, data: run.emit(event, {**data, "id": call_id} if event == "tool_output" else data))
    return await dispatch(scoped, name, arguments)


def decide(chat_id: str, approval_id: str, approved: bool) -> bool:
    run = _runs.get(chat_id)
    pending = run.approvals.get(approval_id) if run else None
    if not pending or pending[1].done():
        return False
    pending[1].set_result(approved)
    return True
