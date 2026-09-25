"""FastAPI app: chat API + SSE, LLM settings, file/library routes, 3D viewer and SPA.

Run (the image's default CMD):
    uvicorn main:app --app-dir /app/web/backend --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import logging
import shutil
import tempfile
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import litellm
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.background import BackgroundTask

import agent
import llm_config
import settings
from paths import rel_to, safe_join
from store import get_store

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

MODEL_SUFFIXES = (".mpd", ".ldr")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".bmp")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    for folder in (settings.GENERATED_DIR, settings.OUTPUT_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    get_store()
    yield


app = FastAPI(title="LeoCAD agent chat", lifespan=lifespan)


def _not_found(what: str = "not found"):
    raise HTTPException(status_code=404, detail=what)


# --- LLM models --------------------------------------------------------------

class LlmEntry(BaseModel):
    model_name: Optional[str] = None
    litellm_params: dict[str, Any]
    capabilities: Optional[dict[str, Any]] = None


@app.get("/api/llm-models")
def llm_models_list():
    entries, default_id = llm_config.list_entries()
    return {"models": [llm_config.public(e) for e in entries], "default_id": default_id}


@app.post("/api/llm-models")
def llm_models_create(entry: LlmEntry):
    try:
        return llm_config.public(llm_config.create(entry.model_dump()))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.put("/api/llm-models/{entry_id}")
def llm_models_update(entry_id: str, entry: LlmEntry):
    try:
        updated = llm_config.update(entry_id, entry.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return llm_config.public(updated) if updated else _not_found()


@app.delete("/api/llm-models/{entry_id}")
def llm_models_delete(entry_id: str):
    return {"deleted": llm_config.delete(entry_id)}


@app.post("/api/llm-models/{entry_id}/default")
def llm_models_default(entry_id: str):
    llm_config.set_default(entry_id)
    return {"default_id": llm_config.list_entries()[1]}


@app.post("/api/llm-models/{entry_id}/test")
async def llm_models_test(entry_id: str):
    entry = llm_config.get(entry_id) or _not_found()
    try:
        response = await litellm.acompletion(
            **llm_config.resolve_params(entry),
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
            max_tokens=20, timeout=60,
        )
        return {"ok": True, "reply": response.choices[0].message.content,
                "capabilities": llm_config.capabilities(entry)}
    except Exception as exc:  # noqa: BLE001 - shown to the user as the test result
        return {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}


@app.get("/api/llm-models/export", response_class=PlainTextResponse)
def llm_models_export():
    entries, _default = llm_config.list_entries()
    model_list = [{"model_name": e["model_name"],
                   "litellm_params": llm_config.public(e)["litellm_params"],
                   "capabilities": e["capabilities"]} for e in entries]
    return yaml.safe_dump({"model_list": model_list}, sort_keys=False, allow_unicode=True)


class ImportBody(BaseModel):
    yaml: str


@app.post("/api/llm-models/import")
def llm_models_import(body: ImportBody):
    try:
        data = yaml.safe_load(body.yaml) or {}
        model_list = data["model_list"] if isinstance(data, dict) else data
        imported = llm_config.import_model_list(model_list)
    except (yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(400, f"not a LiteLLM model_list: {exc}") from None
    return {"imported": [llm_config.public(e) for e in imported]}


@app.get("/api/llm-providers")
def llm_providers():
    names = sorted({getattr(p, "value", p) for p in litellm.provider_list})
    return {"providers": names}


@app.get("/api/llm-providers/{provider}/models")
def llm_provider_models(provider: str):
    models = litellm.models_by_provider.get(provider, [])
    return {"models": sorted(models)}


# --- chats -------------------------------------------------------------------

class NewChat(BaseModel):
    llm_model_id: Optional[str] = None


class ChatPatch(BaseModel):
    title: Optional[str] = None
    llm_model_id: Optional[str] = None


class NewMessage(BaseModel):
    text: str
    llm_model_id: Optional[str] = None


@app.get("/api/chats")
def chats_list():
    chats = get_store().list_chats()
    for chat in chats:
        chat["running"] = agent.is_running(chat["id"])
    return {"chats": chats}


@app.post("/api/chats")
def chats_create(body: NewChat):
    return get_store().create_chat(llm_model_id=body.llm_model_id)


@app.get("/api/chats/{chat_id}")
def chats_get(chat_id: str):
    store = get_store()
    chat = store.get_chat(chat_id) or _not_found("no such chat")
    return {
        "chat": {**chat, "running": agent.is_running(chat_id)},
        "messages": store.messages(chat_id),
        "artifacts": {a["id"]: a for a in store.list_artifacts(chat_id)},
    }


@app.patch("/api/chats/{chat_id}")
def chats_patch(chat_id: str, body: ChatPatch):
    store = get_store()
    store.get_chat(chat_id) or _not_found("no such chat")
    store.update_chat(chat_id, **body.model_dump(exclude_none=True))
    return store.get_chat(chat_id)


@app.delete("/api/chats/{chat_id}")
async def chats_delete(chat_id: str, delete_files: bool = False):
    await agent.cancel(chat_id)
    get_store().delete_chat(chat_id)
    if delete_files:
        shutil.rmtree(settings.GENERATED_DIR / chat_id, ignore_errors=True)
        shutil.rmtree(settings.OUTPUT_DIR / "generated" / chat_id, ignore_errors=True)
    return {"deleted": True}


@app.post("/api/chats/{chat_id}/messages", status_code=202)
async def chats_send(chat_id: str, body: NewMessage):
    store = get_store()
    store.get_chat(chat_id) or _not_found("no such chat")
    if not body.text.strip():
        raise HTTPException(400, "empty message")
    try:
        await agent.start_turn(store, chat_id, body.text, body.llm_model_id)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return {"started": True}


@app.post("/api/chats/{chat_id}/cancel")
async def chats_cancel(chat_id: str):
    return {"cancelled": await agent.cancel(chat_id)}


@app.get("/api/chats/{chat_id}/stream")
async def chats_stream(chat_id: str):
    async def events():
        async for event, data in agent.subscribe(chat_id):
            yield f"event: {event}\ndata: {json.dumps(data)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/artifacts")
def artifacts_list(limit: int = 500):
    return {"artifacts": get_store().list_artifacts(limit=limit)}


# --- data/output browser -----------------------------------------------------

def _source_for(output_file: Path) -> Optional[dict]:
    """The model a render came from: data/X/y.png <- data/X/y.{mpd,ldr}, else a
    reference model with the same stem (renders made from /opt/models-annotated)."""
    rel = output_file.relative_to(settings.OUTPUT_DIR)
    for suffix in (".mpd", ".ldr", ".MPD", ".LDR"):
        candidate = settings.DATA_DIR / rel.with_suffix(suffix)
        if candidate.is_file():
            return {"url": "/files/" + quote(rel_to(candidate, settings.DATA_DIR)), "name": candidate.name}
    for suffix in MODEL_SUFFIXES:
        ref = settings.REF_MODELS_DIR / (output_file.stem + suffix)
        if ref.is_file():
            return {"url": "/ref/" + quote(ref.name), "name": ref.name}
    return None


@app.get("/api/outputs")
def outputs_list(dir: str = ""):
    folder = safe_join(settings.OUTPUT_DIR, dir)
    if folder is None or not folder.is_dir():
        _not_found("no such folder")
    dirs, files = [], []
    for entry in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith("."):
            continue
        rel = rel_to(entry, settings.OUTPUT_DIR)
        if entry.is_dir():
            dirs.append({"name": entry.name, "path": rel})
        else:
            stat = entry.stat()
            files.append({
                "name": entry.name, "path": rel, "size": stat.st_size, "mtime": stat.st_mtime,
                "url": "/files/" + quote(rel_to(entry, settings.DATA_DIR)),
                "is_image": entry.suffix.lower() in IMAGE_SUFFIXES,
                "source": _source_for(entry) if entry.suffix.lower() in IMAGE_SUFFIXES else None,
            })
    return {"dir": rel_to(folder, settings.OUTPUT_DIR) if folder != settings.OUTPUT_DIR.resolve() else "",
            "dirs": dirs, "files": files}


@app.get("/api/outputs/zip")
def outputs_zip(dir: str = ""):
    folder = safe_join(settings.OUTPUT_DIR, dir)
    if folder is None or not folder.is_dir():
        _not_found("no such folder")
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zf.write(path, rel_to(path, folder))
    tmp.close()
    name = (folder.name if dir else "output") + ".zip"
    return FileResponse(tmp.name, filename=name, media_type="application/zip",
                        background=BackgroundTask(Path(tmp.name).unlink, missing_ok=True))


# --- files -------------------------------------------------------------------

def _serve(root: Path, path: str, *, download: bool = False, case_insensitive: bool = False,
           cache: str = "no-cache", media_type: Optional[str] = None) -> FileResponse:
    file = safe_join(root, path, case_insensitive=case_insensitive)
    if file is None or not file.is_file():
        _not_found()
    if media_type is None and file.suffix.lower() in (".dat", ".ldr", ".mpd"):
        media_type = "text/plain; charset=utf-8"
    return FileResponse(file, media_type=media_type, headers={"Cache-Control": cache},
                        filename=file.name if download else None)


@app.get("/files/{path:path}")
def files(path: str, download: bool = False):
    return _serve(settings.DATA_DIR, path, download=download)


@app.get("/ref/{path:path}")
def reference_models(path: str, download: bool = False):
    return _serve(settings.REF_MODELS_DIR, path, download=download, case_insensitive=True,
                  cache="public, max-age=86400")


LIBRARY_CACHE = "public, max-age=31536000, immutable"   # baked into the image, never changes


@app.get("/ldraw/{path:path}")
def ldraw_library(path: str):
    return _serve(settings.LDRAW_DIR, path, case_insensitive=True, cache=LIBRARY_CACHE)


@app.get("/ldraw-id/{part_id:path}")
def ldraw_by_id(part_id: str):
    """A type-1 reference as LDraw resolves it: parts/, then p/, then models/.
    One request per part for the viewer instead of probing each folder (404s)."""
    for sub in ("parts", "p", "models"):
        file = safe_join(settings.LDRAW_DIR / sub, part_id, case_insensitive=True)
        if file is not None and file.is_file():
            return _serve(settings.LDRAW_DIR / sub, part_id, case_insensitive=True, cache=LIBRARY_CACHE)
    _not_found()


# --- viewer + SPA ------------------------------------------------------------

# Vendored viewer libraries (downloaded at build time) and our own viewer page
# live in separate folders, so development can mount web/viewer/ over the page.
if settings.VIEWER_VENDOR_DIR.is_dir():
    app.mount("/viewer/vendor", StaticFiles(directory=settings.VIEWER_VENDOR_DIR), name="viewer-vendor")
if settings.VIEWER_DIR.is_dir():
    app.mount("/viewer", StaticFiles(directory=settings.VIEWER_DIR, html=True), name="viewer")
if (settings.STATIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=settings.STATIC_DIR / "assets"), name="assets")

RESERVED_PREFIXES = ("api/", "files/", "ref/", "ldraw/", "ldraw-id/", "viewer/", "assets/")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str, request: Request):
    if full_path.startswith(RESERVED_PREFIXES):
        return JSONResponse({"detail": "not found"}, status_code=404)
    static = safe_join(settings.STATIC_DIR, full_path) if full_path else None
    if static is not None and static.is_file():
        return FileResponse(static)
    index = settings.STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return PlainTextResponse("Frontend not built: see web/frontend (npm run build).", status_code=404)
