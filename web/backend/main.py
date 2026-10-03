"""FastAPI app: chat API + SSE, LLM settings, file/library routes, 3D viewer and SPA.

Run (the image's default CMD):
    uvicorn main:app --app-dir /app/web/backend --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, unquote, urlsplit

import environment_config

environment_config.initialize()

import litellm
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictInt
from starlette.background import BackgroundTask

import agent
import gallery
import glb
import llm_config
import model_catalog
import model_discovery
import browser_auth
import inference
import render
from attachments import validate_documents, validate_images
import sandbox
import settings
import sculpture
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
    await browser_auth.shutdown()
    for chat_id in list(agent._runs):
        await agent.cancel(chat_id)


app = FastAPI(title="LDraw Nova agent chat", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, exc: RequestValidationError):
    # Pydantic includes submitted values by default, including credentials.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exc.errors()
    ]})


@app.middleware("http")
async def same_origin_api(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (
            origin and urlsplit(origin).netloc != request.headers.get("host")
        ):
            return JSONResponse({"detail": "Cross-origin API requests are not allowed"}, status_code=403)
        try:
            size = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
        if size > 18 * 1024 * 1024:
            return JSONResponse({"detail": "Request exceeds 18 MB"}, status_code=413)
    response = await call_next(request)
    if request.url.path.startswith("/api/environment") or request.url.path.endswith("/edit"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _not_found(what: str = "not found"):
    raise HTTPException(status_code=404, detail=what)


# --- environment overrides --------------------------------------------------

@app.get("/api/environment")
def environment_get():
    return {"variables": environment_config.public()}


@app.get("/api/environment/check")
def environment_check(name: str = "", exclude_id: str = ""):
    return environment_config.check_name(name, exclude_id)


@app.put("/api/environment")
async def environment_save(request: Request):
    # Validate without echoing secret input values in Pydantic error responses.
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, "Expected environment variables as JSON") from None
    if not isinstance(body, dict) or not isinstance(body.get("variables"), list):
        raise HTTPException(400, "Expected a list of environment variables")
    try:
        return {"variables": environment_config.save(body["variables"])}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


# --- LLM models --------------------------------------------------------------

class LlmEntry(BaseModel):
    model_name: Optional[str] = None
    litellm_params: dict[str, Any]
    capabilities: Optional[dict[str, Any]] = None
    auth_mode: str = "api_key"


@app.get("/api/model-catalog")
def model_catalog_list():
    return {"models": [model_catalog.profile(m["model"]) for m in model_catalog.CATALOG]}


@app.get("/api/auth/{provider}")
async def auth_status(provider: str):
    try:
        return await browser_auth.status(provider)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


class LoginRequest(BaseModel):
    flow: str = "browser"
    restart: bool = False


@app.post("/api/auth/{provider}/login")
async def auth_login(provider: str, body: Optional[LoginRequest] = None):
    try:
        return await browser_auth.start(provider, body.flow if body else "browser", body.restart if body else False)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


class AuthCode(BaseModel):
    code: str = Field(max_length=4096)


@app.post("/api/auth/{provider}/code")
async def auth_code(provider: str, body: AuthCode):
    try:
        await browser_auth.submit_code(provider, body.code)
        return {"submitted": True}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.delete("/api/auth/{provider}")
async def auth_disconnect(provider: str):
    if any(agent.is_running(chat_id) for chat_id in agent._runs):
        raise HTTPException(409, "Stop active turns before disconnecting a provider")
    try:
        await browser_auth.disconnect(provider)
        return {"status": "disconnected"}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.get("/api/llm-models")
def llm_models_list():
    entries, default_id = llm_config.builder_entries()
    return {"models": [llm_config.public(e) for e in entries], "default_id": default_id}


@app.get("/api/llm-models/{entry_id}/edit")
def llm_models_edit(entry_id: str):
    entry = llm_config.get(entry_id) or _not_found()
    return llm_config.public(entry)


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
    fingerprint = llm_config.connection_fingerprint(entry)
    discovery = asyncio.create_task(model_discovery.discover(entry))
    async def tested(result):
        metadata = await discovery
        result["connection_status"] = llm_config.record_connection_test(entry_id, fingerprint, result["ok"], metadata)
        result["profile"] = model_catalog.entry_profile(llm_config.get(entry_id) or entry)
        return result
    try:
        if entry.get("auth_mode") == "browser" and entry["litellm_params"]["model"].startswith("anthropic/"):
            ready = await browser_auth.connected("anthropic")
            return await tested({"ok": ready, "reply": "Claude login is ready. Send a chat to verify model access." if ready else None,
                           "error": None if ready else "Sign in to Claude in Settings first"})
        params = await inference.params_for(entry, {})
        params.setdefault("max_tokens", 4096)
        params.setdefault("timeout", 60)
        response = await litellm.acompletion(
            **params,
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
        )
        return await tested({"ok": True, "reply": "Connection successful.",
                       "capabilities": llm_config.capabilities(entry)})
    except Exception as exc:  # noqa: BLE001 - shown to the user as the test result
        return await tested({"ok": False, "error": f"{exc.__class__.__name__}: Check credentials, model access and settings."})


@app.get("/api/llm-models/export", response_class=PlainTextResponse)
def llm_models_export():
    entries, _default = llm_config.builder_entries()
    model_list = [{"model_name": e["model_name"],
                   "litellm_params": llm_config.public(e)["litellm_params"],
                   "capabilities": e["capabilities"], "auth_mode": e.get("auth_mode", "api_key")} for e in entries]
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
    presets = [m["model"] for m in model_catalog.CATALOG if m["model"].startswith(provider + "/")]
    candidates = {m if m.startswith(provider + "/") else provider + "/" + m for m in models} | set(presets)
    return {"models": sorted(m for m in candidates if model_catalog.builder_supported(m))}


# --- chats -------------------------------------------------------------------

class NewChat(BaseModel):
    llm_model_id: Optional[str] = None


class ChatPatch(BaseModel):
    title: Optional[str] = None
    llm_model_id: Optional[str] = None


class NewMessage(BaseModel):
    text: str = Field(max_length=200_000)
    llm_model_id: Optional[str] = None
    options: dict[str, Any] = Field(default_factory=dict)
    images: list[str] = Field(default_factory=list, max_length=4)
    documents: list[dict[str, Any]] = Field(default_factory=list, max_length=4)


# --- model helpers -------------------------------------------------------------

def is_gallery(path: Path) -> bool:
    """A file from the gallery baked into the image."""
    return path.parent.resolve() == settings.GALLERY_MODELS_DIR.resolve()


def file_url(path: Path, versioned: bool = False) -> Optional[str]:
    """URL of an existing file the web UI may load, else None: /files/... in a
    web-visible folder of /data (generated/, chats/), or /gallery-files/... for gallery
    models. data/output is agent-only: never served.

    `versioned` adds the file's mtime, for images that can be re-rendered under
    the same name: browsers reuse an image already on the page by URL alone."""
    if is_gallery(path):
        url = "/gallery-files/" + quote(path.name)
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


def _status(path: Path, kind: str, in_gallery: bool) -> tuple[str, Optional[str]]:
    if not in_gallery:
        return gallery.status_of(path, kind)
    # Gallery models come with their siblings: nothing is made for them.
    sibling = snapshot_path_for(path) if kind == "snapshot" else bom_path_for(path)
    return ("ready", None) if sibling.exists() else ("failed", "none included with this gallery model")


def model_info(path: Path) -> dict:
    """A model file in the collection, as the UI sees it: its snapshot (status,
    image_url), BOM (bom_status, bom_url), part count (from the BOM), notes
    (info_url and info_heading, from its .md) and its collection."""
    exists = path.is_file()
    in_gallery = is_gallery(path)
    status, error = _status(path, "snapshot", in_gallery) if exists else ("missing", None)
    bom_status, bom_error = _status(path, "bom", in_gallery) if exists else ("missing", None)
    stat = path.stat() if exists else None
    return {
        "file": path.name, "name": path.stem, "description": gallery.description_of(path) if exists else "",
        "model_url": file_url(path), "image_url": file_url(snapshot_path_for(path), versioned=True),
        "bom_url": file_url(bom_path_for(path), versioned=True), "parts": gallery.part_count(path) if exists else None,
        "info_url": file_url(gallery.info_path_for(path), versioned=True), "gallery": in_gallery,
        "info_heading": gallery.info_heading_of(path) if exists else None,
        "size": stat.st_size if stat else 0, "mtime": stat.st_mtime if stat else 0,
        "status": status, "error": error, "bom_status": bom_status, "bom_error": bom_error,
        "sculpture": bool(exists and not in_gallery and sculpture.read(path)),
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
        m.pop("_reasoning_details", None)  # opaque provider state belongs only in server-side history
        if m.get("_images"):
            m["_image_urls"] = [u for u in (file_url(store.resolve(chat_id, r), versioned=True) for r in m["_images"]) if u]
        if m.get("_documents"):
            for document in m["_documents"]:
                path = store.resolve(chat_id, document["path"])
                try:
                    relative = path.relative_to(store.work_dir(chat_id))
                    document["url"] = f"/api/chats/{chat_id}/artifacts/" + quote(relative.as_posix())
                except ValueError:
                    document["url"] = None
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
        images = validate_images(body.images)
        documents = validate_documents(body.documents, images)
        await agent.start_turn(store, chat_id, body.text, body.llm_model_id, body.options, images, documents)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return {"started": True}


class ApprovalDecision(BaseModel):
    approved: bool


@app.post("/api/chats/{chat_id}/approvals/{approval_id}")
async def chats_approve(chat_id: str, approval_id: str, body: ApprovalDecision):
    if not agent.decide(chat_id, approval_id, body.approved):
        raise HTTPException(409, "This approval is no longer pending")
    return {"accepted": True}


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


@app.get("/api/chats/{chat_id}/artifacts/{path:path}")
def chat_artifact(chat_id: str, path: str):
    """Explicit downloads from one chat's output; never expose runtime/config.

    HTML catalogs are downloadable, but are not executed with app privileges.
    """
    store = get_store()
    store.get_chat(chat_id) or _not_found("no such chat")
    if any(part.startswith(".") for part in Path(path).parts):
        _not_found()
    file = safe_join(store.work_dir(chat_id), path)
    if not file or not file.is_file():
        _not_found()
    return FileResponse(file, filename=file.name, headers={
        "Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox; default-src 'none'",
    })


# --- model collections (My Models and Gallery) ---------------------------------


@app.get("/api/models")
async def models_list():
    """Every model in data/generated, newest first. Models without a snapshot
    or BOM get them made in the background; poll until
    `pending` is 0."""
    models = gallery.collection(settings.GENERATED_DIR)
    gallery.ensure_artifacts(models)
    index = model_chat_index(get_store())
    items = [{**model_info(path), "chats": index.get(path, [])} for path in models]
    return {"models": items, "pending": sum(1 for i in items if _pending(i))}


@app.get("/api/gallery")
def gallery_list():
    """The bundled gallery, independent of generated models with the same name."""
    return {"models": [model_info(path) for path in gallery.collection(settings.GALLERY_MODELS_DIR)], "pending": 0}


def editable_model(filename: str) -> tuple[Path, dict]:
    path = settings.GENERATED_DIR / filename
    if Path(filename).name != filename or filename.startswith(".") or path.suffix.lower() not in {".mpd", ".ldr"}:
        _not_found("Sculpture model not found")
    data = sculpture.read(path)
    if data is None:
        _not_found("No editable sculpture is saved for this model")
    return path, data


@app.get("/api/models/{filename}/sculpture")
def sculpture_get(filename: str):
    _, data = editable_model(filename)
    return {**data, "palette": sculpture.palette()}


class SculptureEdit(BaseModel):
    voxels: list[list[StrictInt]] = Field(min_length=1, max_length=65536)
    revision: str


@app.post("/api/models/{filename}/sculpture")
async def sculpture_save(filename: str, body: SculptureEdit):
    import uuid
    import tools
    path, original = editable_model(filename)
    if body.revision != original["revision"]:
        raise HTTPException(409, "This model changed. Reopen the sculpture editor before saving.")
    try:
        sculpture.validate_rows(body.voxels)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    store = get_store()
    # An edit chat keeps generation permissions and in-progress chats independent.
    chat = store.create_chat()
    store.update_chat(chat["id"], title=f"Edit {path.stem}", options={"build_style": "sculpture"})
    ctx = tools.ToolContext(chat["id"], store, lambda *_: None)
    stem = "sculpture-" + uuid.uuid4().hex[:12]
    source = ctx.work_dir / (stem + ".voxels.json")
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps({"voxels": body.voxels}))
    sandbox.give_to_agent(source.parent)
    sandbox.give_to_agent(source)
    await tools.t_run_toolkit(ctx, ["sculpture", "output/" + stem + ".voxels.json",
        "--output", "output/" + stem + ".mpd", "--title", gallery.description_of(path) or path.stem,
        "--report", "output/" + stem + ".checks.json"], timeout=300)
    report_path = ctx.work_dir / (stem + ".checks.json")
    report = json.loads(report_path.read_text()) if report_path.is_file() else {}
    if not report.get("checks_passed"):
        raise HTTPException(422, report.get("error") or "Connectivity repair could not finish. Your original model is preserved; adjust the sculpture and try again.")
    published = await tools.t_publish_model(ctx, "output/" + stem + ".mpd", path.stem + " edited")
    if not published.models:
        raise HTTPException(422, "The edited model could not be published. Your original model is preserved.")
    ref = published.models[0]
    published_path = store.resolve(chat["id"], ref["model"])
    repaired = sculpture.read(published_path)
    if repaired is None:
        raise HTTPException(422, "The saved model has no matching editable voxels. Your original model is preserved.")
    model = model_info(published_path)
    return {"model": model, "chat_id": chat["id"], "voxels": repaired["voxels"],
            "support_voxels": report.get("interior_support_voxels", 0) + report.get("exterior_support_voxels", 0)}


@app.delete("/api/models/{filename}")
async def models_delete(filename: str):
    root = settings.GENERATED_DIR.resolve()
    # Delete only a direct, regular model file. Never follow a link or accept a
    # URL/path supplied by a card, including links into the read-only Gallery.
    model = root / filename
    if (Path(filename).name != filename or filename.startswith(".")
            or model.suffix.lower() not in MODEL_SUFFIXES or model.is_symlink()
            or not model.is_file()):
        _not_found("Model not found")
    if model in gallery.publishing or gallery._current == model or render.is_busy(model) or glb.is_converting(model):
        raise HTTPException(409, "This model is still being processed. Try deleting it again when processing finishes.")
    # Notes/previews are shared if car.mpd and car.ldr both exist: retain those.
    shared = any(p != model and p.stem == model.stem for p in gallery.collection(root))
    artifacts = [] if shared else [model.with_suffix(ext) for ext in (".png", ".csv", ".md", ".glb")]
    targets = [model, *artifacts, *sculpture.siblings(model), *glb.cache_files(model)]
    deleted = []
    for path in targets:
        if path.is_file() and not path.is_symlink():
            path.unlink()
            deleted.append(path.name)
    gallery.forget(model)
    # Keep chat records as history. Their existing missing-model state explains
    # that a model is gone, while the agent's original work files remain intact.
    return {"deleted": deleted}


def model_from_url(url: str) -> Optional[Path]:
    """Resolve generated and gallery viewer URLs, including old /demo/ links."""
    path = unquote(urlsplit(url).path)
    for prefix, root in (("/files/generated/", settings.GENERATED_DIR),
                         ("/gallery-files/", settings.GALLERY_MODELS_DIR),
                         ("/demo/", settings.GALLERY_MODELS_DIR)):
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
    model = model_from_url(url) or _not_found("not a model in My Models or Gallery")
    try:
        out = await glb.export_glb(model)
    except glb.GlbError as exc:
        raise HTTPException(500, str(exc)) from None
    return FileResponse(out, media_type="model/gltf-binary", filename=model.stem + ".glb",
                        headers={"Cache-Control": "no-cache"})


def collection_zip(folder: Path, filename: str):
    """Download one collection with its snapshots, BOMs and notes."""
    files = [p for p in sorted(folder.iterdir()) if p.is_file() and not p.name.startswith(".")] if folder.is_dir() else []
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.name)
    tmp.close()
    return FileResponse(tmp.name, filename=filename, media_type="application/zip",
                        background=BackgroundTask(Path(tmp.name).unlink, missing_ok=True))


@app.get("/api/models/zip")
def models_zip():
    return collection_zip(settings.GENERATED_DIR, "generated.zip")


@app.get("/api/gallery/zip")
def gallery_zip():
    return collection_zip(settings.GALLERY_MODELS_DIR, "gallery.zip")


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


@app.get("/demo/{path:path}", include_in_schema=False)  # preserve existing viewer links
@app.get("/gallery-files/{path:path}")
def gallery_files(path: str, download: bool = False):
    """The gallery models baked into the image, with their snapshots, BOMs and notes."""
    return _serve(settings.GALLERY_MODELS_DIR, path, download=download)


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

RESERVED_PREFIXES = ("api/", "files/", "gallery-files/", "demo/", "ldraw/", "ldraw-id/", "viewer/", "xr/", "assets/")


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
