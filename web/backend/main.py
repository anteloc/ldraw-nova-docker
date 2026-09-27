"""FastAPI app: chat API + SSE, LLM settings, file/library routes, 3D viewer and SPA.

Run (the image's default CMD):
    uvicorn main:app --app-dir /app/web/backend --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import logging
import tempfile
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, unquote, urlsplit

import litellm
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.background import BackgroundTask

import agent
import gallery
import glb
import llm_config
import sandbox
import settings
from leocad_render import MODEL_SUFFIXES, bom_path_for, snapshot_path_for
from paths import rel_to, safe_join
from store import ChatStore, get_store

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    for folder in (settings.GENERATED_DIR, settings.CHATS_DIR, settings.OUTPUT_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    sandbox.give_to_agent(settings.GENERATED_DIR)      # agent scripts may publish models there
    get_store()
    yield


app = FastAPI(title="LDraw Astra agent chat", lifespan=lifespan)


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


# --- model helpers -------------------------------------------------------------

def is_demo(path: Path) -> bool:
    """A file of the demo models baked into the image."""
    return path.parent.resolve() == settings.DEMO_MODELS_DIR.resolve()


def file_url(path: Path, versioned: bool = False) -> Optional[str]:
    """URL of an existing file the web UI may load, else None: /files/... in a
    web-visible folder of /data (generated/, chats/), or /demo/... for the demo
    models. data/output is agent-only: never served.

    `versioned` adds the file's mtime, for images that can be re-rendered under
    the same name: browsers reuse an image already on the page by URL alone."""
    if is_demo(path):
        url = "/demo/" + quote(path.name)
    else:
        try:
            rel = rel_to(path, settings.DATA_DIR)
        except ValueError:
            return None
        if rel.split("/", 1)[0] not in settings.WEB_DIRS:
            return None
        url = "/files/" + quote(rel)
    if not path.is_file():
        return None
    return f"{url}?v={path.stat().st_mtime_ns}" if versioned else url


def _status(path: Path, kind: str, demo: bool) -> tuple[str, Optional[str]]:
    if not demo:
        return gallery.status_of(path, kind)
    # demo models come with their siblings: nothing is made for them
    sibling = snapshot_path_for(path) if kind == "snapshot" else bom_path_for(path)
    return ("ready", None) if sibling.exists() else ("failed", "none included with this demo model")


def model_info(path: Path) -> dict:
    """A model file in the collection, as the UI sees it: its snapshot (status,
    image_url), BOM (bom_status, bom_url), part count (from the BOM), notes
    (info_url, its .md) and whether it's one of the demo models."""
    exists = path.is_file()
    demo = is_demo(path)
    status, error = _status(path, "snapshot", demo) if exists else ("missing", None)
    bom_status, bom_error = _status(path, "bom", demo) if exists else ("missing", None)
    stat = path.stat() if exists else None
    return {
        "file": path.name, "name": path.stem, "description": gallery.description_of(path) if exists else "",
        "model_url": file_url(path), "image_url": file_url(snapshot_path_for(path), versioned=True),
        "bom_url": file_url(bom_path_for(path), versioned=True), "parts": gallery.part_count(path) if exists else None,
        "info_url": file_url(gallery.info_path_for(path), versioned=True), "demo": demo,
        "size": stat.st_size if stat else 0, "mtime": stat.st_mtime if stat else 0,
        "status": status, "error": error, "bom_status": bom_status, "bom_error": bom_error,
    }


def _pending(info: dict) -> bool:
    return info["status"] in ("queued", "rendering") or info["bom_status"] in ("queued", "rendering")


def chat_models(store: ChatStore, chat_id: str) -> dict[str, dict]:
    """The models a chat produced (references into data/generated), keyed by id."""
    result = {}
    for ref in store.models(chat_id):
        path = store.resolve(chat_id, ref["model"])
        result[ref["id"]] = {**model_info(path), "id": ref["id"], "name": ref["name"],
                             "warnings": ref.get("warnings", []), "created_at": ref["created_at"]}
    return result


def model_chat_index(store: ChatStore) -> dict[Path, list[dict]]:
    """model path -> the chats that produced it."""
    index: dict[Path, list[dict]] = {}
    for chat in store.list_chats():
        for ref in store.models(chat["id"]):
            chats = index.setdefault(store.resolve(chat["id"], ref["model"]), [])
            if not any(c["id"] == chat["id"] for c in chats):
                chats.append({"id": chat["id"], "title": chat["title"]})
    return index


# --- chats ---------------------------------------------------------------------

@app.get("/api/chats")
def chats_list():
    store = get_store()
    chats = store.list_chats()
    for chat in chats:
        chat["running"] = agent.is_running(chat["id"])
        chat["models"] = list(chat_models(store, chat["id"]).values())
    return {"chats": chats}


@app.post("/api/chats")
def chats_create(body: NewChat):
    return get_store().create_chat(llm_model_id=body.llm_model_id)


@app.get("/api/chats/{chat_id}")
async def chats_get(chat_id: str):
    store = get_store()
    chat = store.get_chat(chat_id) or _not_found("no such chat")
    messages = store.messages(chat_id)
    for m in messages:
        if m.get("_images"):
            m["_image_urls"] = [u for u in (file_url(store.resolve(chat_id, r), versioned=True) for r in m["_images"]) if u]
    models = chat_models(store, chat_id)
    gallery.ensure_artifacts(store.resolve(chat_id, ref["model"]) for ref in store.models(chat_id)
                             if store.resolve(chat_id, ref["model"]).is_file())
    return {"chat": {**chat, "running": agent.is_running(chat_id)}, "messages": messages, "models": models}


@app.patch("/api/chats/{chat_id}")
def chats_patch(chat_id: str, body: ChatPatch):
    store = get_store()
    store.get_chat(chat_id) or _not_found("no such chat")
    store.update_chat(chat_id, **body.model_dump(exclude_none=True))
    return store.get_chat(chat_id)


@app.delete("/api/chats/{chat_id}")
async def chats_delete(chat_id: str):
    """Deletes data/chats/<id> and its work folder data/output/<id>. The models
    it produced stay in data/generated (they're part of the collection)."""
    store = get_store()
    store.get_chat(chat_id) or _not_found("no such chat")
    await agent.cancel(chat_id)
    store.delete_chat(chat_id)
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


# --- the model collection (data/generated, plus the demo models) ---------------------

def gallery_models() -> list[Path]:
    """data/generated (newest first), then the demo models it doesn't override."""
    return gallery.with_demos(gallery.collection(settings.GENERATED_DIR), settings.DEMO_MODELS_DIR)


@app.get("/api/models")
async def models_list():
    """Every model in data/generated, newest first, then the demo models (a
    model in data/generated overrides a demo model of the same name). Models
    without a snapshot or BOM get them made in the background; poll until
    `pending` is 0."""
    models = gallery_models()
    gallery.ensure_artifacts(m for m in models if not is_demo(m))   # demo models ship with theirs
    index = model_chat_index(get_store())
    items = [{**model_info(path), "chats": index.get(path, [])} for path in models]
    return {"models": items, "pending": sum(1 for i in items if _pending(i))}


def model_from_url(url: str) -> Optional[Path]:
    """The model file behind a viewer URL: /files/generated/<name> or /demo/<name>."""
    path = unquote(urlsplit(url).path)
    for prefix, root in (("/files/generated/", settings.GENERATED_DIR), ("/demo/", settings.DEMO_MODELS_DIR)):
        if path.startswith(prefix):
            model = safe_join(root, path[len(prefix):])
            if (model is not None and model.is_file() and model.parent == root.resolve()
                    and model.suffix.lower() in MODEL_SUFFIXES):
                return model
    return None


@app.get("/api/glb")
async def model_glb(url: str):
    """The model at `url` (as the viewer loads it) as an uncompressed .glb, made
    with mpd2glb. Can take a minute for big models; cached per model version."""
    model = model_from_url(url) or _not_found("not a model in data/generated or the demo models")
    try:
        out = await glb.export_glb(model)
    except glb.GlbError as exc:
        raise HTTPException(500, str(exc)) from None
    return FileResponse(out, media_type="model/gltf-binary", filename=model.stem + ".glb",
                        headers={"Cache-Control": "no-cache"})


@app.get("/api/models/zip")
def models_zip():
    """Everything on the Models page as a zip: data/generated (every model with
    its snapshot, BOM and notes), plus the demo models shown with it."""
    demos = {m.stem for m in gallery_models() if is_demo(m)}
    files = [p for p in sorted(settings.GENERATED_DIR.iterdir()) if p.is_file() and not p.name.startswith(".")]
    if settings.DEMO_MODELS_DIR.is_dir():
        files += [p for p in sorted(settings.DEMO_MODELS_DIR.iterdir()) if p.is_file() and p.stem in demos]
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        written = set()
        for path in files:
            if path.name not in written:
                zf.write(path, path.name)
                written.add(path.name)
    tmp.close()
    return FileResponse(tmp.name, filename="generated.zip", media_type="application/zip",
                        background=BackgroundTask(Path(tmp.name).unlink, missing_ok=True))


# --- files -------------------------------------------------------------------

def _serve(root: Path, path: str, *, download: bool = False, case_insensitive: bool = False,
           cache: str = "no-cache", media_type: Optional[str] = None,
           headers: Optional[dict[str, str]] = None) -> FileResponse:
    file = safe_join(root, path, case_insensitive=case_insensitive)
    if file is None or not file.is_file():
        _not_found()
    if media_type is None and file.suffix.lower() in (".dat", ".ldr", ".mpd"):
        media_type = "text/plain; charset=utf-8"
    elif media_type is None and file.suffix.lower() == ".md":
        media_type = "text/markdown; charset=utf-8"
    return FileResponse(file, media_type=media_type, headers={"Cache-Control": cache, **(headers or {})},
                        filename=file.name if download else None)


@app.get("/files/{path:path}")
def files(path: str, download: bool = False):
    """Files in data/generated and data/chats. Checked on the resolved path, so
    generated/../output/... can't reach the agents' work folders."""
    file = safe_join(settings.DATA_DIR, path)
    if file is None or file_url(file) is None:
        _not_found()
    return _serve(settings.DATA_DIR, path, download=download)


@app.get("/demo/{path:path}")
def demo_models(path: str, download: bool = False):
    """The demo models baked into the image, with their snapshots, BOMs and notes."""
    return _serve(settings.DEMO_MODELS_DIR, path, download=download)


LIBRARY_CACHE = "public, max-age=31536000, immutable"   # baked into the image, never changes


@app.get("/ldraw/{path:path}")
def ldraw_library(path: str):
    return _serve(settings.LDRAW_DIR, path, case_insensitive=True, cache=LIBRARY_CACHE)


@app.get("/ldraw-id/{part_id:path}")
def ldraw_by_id(part_id: str):
    """A type-1 reference as LDraw resolves it: parts/, then p/, then models/.
    One request per part for the viewer and player instead of probing each
    folder (404s). X-LDraw-Folder says which folder it came from: the player
    treats p/ files as primitives."""
    for sub in ("parts", "p", "models"):
        file = safe_join(settings.LDRAW_DIR / sub, part_id, case_insensitive=True)
        if file is not None and file.is_file():
            return _serve(settings.LDRAW_DIR / sub, part_id, case_insensitive=True, cache=LIBRARY_CACHE,
                          headers={"X-LDraw-Folder": sub})
    _not_found()


# --- viewer + SPA ------------------------------------------------------------

class RevalidatedStaticFiles(StaticFiles):
    """Static files browsers must check with us before reusing a cached copy (a
    quick 304 while unchanged). Without Cache-Control, browsers reuse one for a
    while without asking, so after an image rebuild a page can run the previous
    version: e.g. an old player's .js and .wasm, whose URLs never change."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers.setdefault("Cache-Control", "no-cache")
        return response


# Vendored viewer and player libraries (added at build time) and our own pages
# (viewer.html, player.html) live in separate folders, so development can mount
# web/viewer/ over the pages.
if settings.VIEWER_VENDOR_DIR.is_dir():
    app.mount("/viewer/vendor", RevalidatedStaticFiles(directory=settings.VIEWER_VENDOR_DIR), name="viewer-vendor")
if settings.PLAYER_VENDOR_DIR.is_dir():
    app.mount("/viewer/player-vendor", RevalidatedStaticFiles(directory=settings.PLAYER_VENDOR_DIR),
              name="player-vendor")
if settings.VIEWER_DIR.is_dir():
    app.mount("/viewer", RevalidatedStaticFiles(directory=settings.VIEWER_DIR, html=True), name="viewer")
# The mixed-reality viewer (web/xr, built in the image): /xr/?model=<url>
if settings.XR_DIR.is_dir():
    app.mount("/xr", RevalidatedStaticFiles(directory=settings.XR_DIR, html=True), name="xr")
if (settings.STATIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=settings.STATIC_DIR / "assets"), name="assets")

RESERVED_PREFIXES = ("api/", "files/", "demo/", "ldraw/", "ldraw-id/", "viewer/", "xr/", "assets/")


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
