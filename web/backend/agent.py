"""Provider-agnostic agent loop on top of LiteLLM.

A turn runs as a background asyncio task per chat (so reloading the page
doesn't kill it). The database is the source of truth; live events only carry
what's in flight (streaming text, running tools) plus "saved" pings telling
the UI to refetch.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import litellm

import llm_config
import settings
from store import Store
from tools import TOOL_SCHEMAS, ToolContext, dispatch

log = logging.getLogger("agent")

litellm.drop_params = True            # ignore params a provider doesn't support
litellm.suppress_debug_info = True

MAX_STEPS = 30
KEEP_IMAGE_MESSAGES = 2               # only the newest renders are re-sent to vision models


@dataclass
class Run:
    chat_id: str
    task: Optional[asyncio.Task] = None
    draft: str = ""
    tools_running: dict[str, dict] = field(default_factory=dict)
    subscribers: set[asyncio.Queue] = field(default_factory=set)

    def emit(self, event: str, data: dict) -> None:
        for queue in list(self.subscribers):
            queue.put_nowait((event, data))


_runs: dict[str, Run] = {}


def is_running(chat_id: str) -> bool:
    run = _runs.get(chat_id)
    return bool(run and run.task and not run.task.done())


def system_prompt(chat_id: str) -> str:
    text = (settings.PROMPTS_DIR / "system.md").read_text()
    return (text.replace("{workspace}", str(settings.GENERATED_DIR / chat_id))
                .replace("{ldraw_dir}", str(settings.LDRAW_DIR)))


def _image_data_url(rel_path: str) -> Optional[str]:
    path = settings.DATA_DIR / rel_path
    if not path.is_file():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def llm_history(messages: list[dict], vision: bool) -> list[dict]:
    """Stored messages -> what we send to the LLM.

    Drops UI-only notes and our "_" metadata, re-attaches only the newest
    renders for vision models, and repairs tool calls left without results
    (a stopped or crashed turn) so providers accept the history.
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
            urls = [u for u in map(_image_data_url, m["_images_for_llm"]) if u]
            content = [{"type": "text", "text": m["content"]}]
            content += [{"type": "image_url", "image_url": {"url": u}} for u in urls]
            out.append({"role": "user", "content": content})
            continue
        clean = {k: v for k, v in m.items() if not k.startswith("_") and k not in ("id", "created_at")}
        out.append(clean)
        pending.extend(tc["id"] for tc in m.get("tool_calls") or [])
    close_pending()
    return out


async def start_turn(store: Store, chat_id: str, text: str, llm_model_id: Optional[str]) -> None:
    if is_running(chat_id):
        raise RuntimeError("this chat is already running a turn")
    entry = llm_config.get(llm_model_id) if llm_model_id else None
    if entry is None:
        _entries, default_id = llm_config.list_entries()
        entry = llm_config.get(default_id) if default_id else None
    if entry is None:
        raise ValueError("no LLM model configured — add one in Settings")

    chat = store.get_chat(chat_id)
    if chat["title"] == "New chat":
        title = " ".join(text.split())
        store.update_chat(chat_id, title=title[:60] + ("…" if len(title) > 60 else ""))
    store.update_chat(chat_id, llm_model_id=entry["id"])
    store.add_message(chat_id, {"role": "user", "content": text})

    run = _runs.get(chat_id) or Run(chat_id)
    _runs[chat_id] = run
    run.draft, run.tools_running = "", {}
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
    queue: asyncio.Queue = asyncio.Queue()
    run.subscribers.add(queue)
    try:
        yield "snapshot", {"running": True, "draft": run.draft, "tools": list(run.tools_running.values())}
        while True:
            try:
                event, data = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                yield "ping", {}                  # keeps proxies/browsers from timing out
                continue
            yield event, data
            if event == "done":
                return
    finally:
        run.subscribers.discard(queue)


async def _run_turn(store: Store, run: Run, entry: dict) -> None:
    chat_id = run.chat_id
    caps = llm_config.capabilities(entry)
    vision = caps["vision"] is True
    use_tools = caps["tools"] is not False
    ctx = ToolContext(chat_id=chat_id, store=store, emit=run.emit)

    def save(message: dict) -> int:
        msg_id = store.add_message(chat_id, message)
        run.emit("saved", {"message_id": msg_id})
        return msg_id

    try:
        params = llm_config.resolve_params(entry)
        for _step in range(MAX_STEPS):
            messages = [{"role": "system", "content": system_prompt(chat_id)},
                        *llm_history(store.messages(chat_id), vision)]
            kwargs = {"tools": TOOL_SCHEMAS} if use_tools else {}
            stream = await litellm.acompletion(**params, messages=messages, stream=True, num_retries=2, **kwargs)

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
            if tool_calls:
                message["tool_calls"] = tool_calls
            if getattr(reply, "thinking_blocks", None):          # must round-trip for Anthropic thinking
                message["thinking_blocks"] = reply.thinking_blocks
            if getattr(reply, "reasoning_content", None):
                message["_reasoning"] = reply.reasoning_content
            if not message["content"] and not tool_calls:
                break                                              # nothing to save or do
            save(message)
            run.draft = ""
            if not tool_calls:
                break

            images: list[str] = []
            for call in tool_calls:
                name = call["function"]["name"]
                run.tools_running[call["id"]] = {"id": call["id"], "name": name,
                                                 "arguments": call["function"]["arguments"]}
                run.emit("tool_start", run.tools_running[call["id"]])
                result = await dispatch(ctx, name, call["function"]["arguments"])
                run.tools_running.pop(call["id"], None)
                save({"role": "tool", "tool_call_id": call["id"], "name": name, "content": result.content,
                      "_artifacts": [a["id"] for a in result.artifacts], "_images": result.images})
                run.emit("tool_end", {"id": call["id"], "name": name})
                images += result.images
            if images and vision:
                save({"role": "user", "content": "Renders produced by the tool calls above:",
                      "_images_for_llm": images, "_hidden": True})
        else:
            save({"role": "assistant", "_ui_only": True, "_notice": True,
                  "content": f"Stopped after {MAX_STEPS} steps. Send a message to continue."})
    except asyncio.CancelledError:
        if run.draft:
            save({"role": "assistant", "content": run.draft})
        save({"role": "assistant", "_ui_only": True, "_notice": True, "content": "Stopped."})
        raise
    except Exception as exc:  # noqa: BLE001 - provider/auth/network errors end the turn, not the chat
        log.exception("turn failed for chat %s", chat_id)
        message = f"{exc.__class__.__name__}: {exc}"
        save({"role": "assistant", "_ui_only": True, "_error": True, "content": message})
        run.emit("turn_error", {"message": message})   # not "error": EventSource reserves it
    finally:
        run.draft, run.tools_running = "", {}
        run.emit("done", {})
