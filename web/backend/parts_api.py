"""Owned parts API; fitted models use the ordinary validated publication flow."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, StrictInt
import owned_parts
import parts_catalog
import settings

router = APIRouter(prefix="/api/my-parts")
_catalog_task = None
_state = {"building": False, "stage": "Not downloaded", "error": None}
_fit_lock = asyncio.Lock()


def catalog_status():
    return {**parts_catalog.status(), **_state}


@router.get("")
def read(query: str = ""):
    if len(query) > 160:
        raise HTTPException(422, "Keep searches below 160 characters")
    return {**owned_parts.inventory(query), "catalog": catalog_status()}


@router.post("/catalog")
async def index_catalog():
    global _catalog_task
    if _state["building"]:
        raise HTTPException(429, "Catalog indexing is already running")
    _state.update(building=True, stage="Downloading public catalog", error=None)

    async def run():
        try:
            await asyncio.to_thread(
                parts_catalog.build, lambda stage: _state.update(stage=stage)
            )
        except Exception:
            _state.update(
                error="Catalog download failed. Retry; your previous catalog and owned parts are unchanged.",
                stage="Download failed",
            )
        finally:
            _state["building"] = False

    _catalog_task = asyncio.create_task(run())
    return catalog_status()


@router.get("/sets")
def sets(query: str = ""):
    if len(query) > 160:
        raise HTTPException(422, "Keep searches below 160 characters")
    return {"sets": parts_catalog.search(query), "catalog": catalog_status()}


@router.get("/find")
def find(query: str = ""):
    import ldraw

    if len(query) > 160:
        raise HTTPException(422, "Keep searches below 160 characters")
    return {"parts": ldraw.find_parts(query, limit=20)}


@router.post("/upload")
async def upload(
    request: Request,
    system: Literal["ldraw", "bricklink", "rebrickable"] = "ldraw",
    label: str = "Uploaded parts",
):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > owned_parts.MAX_UPLOAD:
            raise HTTPException(413, "Parts list exceeds 2 MB")
    try:
        return owned_parts.add(owned_parts.parse_upload(bytes(raw), system), label)
    except UnicodeError:
        raise HTTPException(
            422, "Use a UTF-8 CSV/XML parts export, not a PDF or other binary file"
        ) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except (KeyError, TypeError):
        raise HTTPException(
            422,
            "Import needs CSV part/color/quantity columns or BrickLink INVENTORY XML with positive quantities",
        ) from None


class UrlImport(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    system: Literal["ldraw", "bricklink", "rebrickable"] = "bricklink"
    copies: StrictInt = Field(default=1, ge=1, le=100)


@router.post("/import-url")
async def url_import(body: UrlImport):
    try:
        number = parts_catalog.set_number(body.url)
        if number:
            rows = await asyncio.to_thread(parts_catalog.inventory, number, body.copies)
            label = (
                number
                + " ("
                + str(body.copies)
                + " set"
                + ("s" if body.copies != 1 else "")
                + ")"
            )
        else:
            raw = await asyncio.to_thread(
                parts_catalog.download, body.url, owned_parts.MAX_UPLOAD
            )
            if raw.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                raise ValueError(
                    "This source is a web page or requires sign-in. Download its CSV/XML export in your browser and upload it instead."
                )
            rows = owned_parts.parse_upload(raw, body.system)
            label = "Imported URL"
        return owned_parts.add(rows, label)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception:
        raise HTTPException(
            422,
            "Cannot fetch this export. Download its CSV/XML in your browser and upload it instead.",
        ) from None


class Lot(BaseModel):
    part: str = Field(min_length=1, max_length=80)
    color: StrictInt
    quantity: StrictInt = Field(ge=1, le=1000000)


@router.post("/lots")
def add_lot(body: Lot):
    try:
        rows = owned_parts.normalize([body.model_dump()], "ldraw")
        if rows[0]["part"] is None or rows[0]["color"] is None:
            raise ValueError("Choose an installed part and explicit LDraw color")
        return owned_parts.add(rows, "Loose parts")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.put("/lots/{lot}")
def edit_lot(lot: str, body: Lot):
    try:
        return owned_parts.edit(lot, body.part, body.color, body.quantity)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


class FitRequest(BaseModel):
    file: str = Field(max_length=160)
    revision: str = Field(max_length=64)


@router.post("/fit")
async def fit_model(body: FitRequest):
    import hashlib
    import tools
    import sandbox
    from store import get_store
    from main import model_info

    source = settings.GENERATED_DIR / body.file
    if (
        Path(body.file).name != body.file
        or source.is_symlink()
        or not source.is_file()
        or source.suffix.lower() not in (".mpd", ".ldr")
    ):
        raise HTTPException(404, "Choose a saved model from My Models")
    if source.stat().st_size > 32 * 1024 * 1024:
        raise HTTPException(413, "Model exceeds 32 MB")
    source_bytes = source.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != body.revision:
        raise HTTPException(409, "Model changed. Refresh My Models and try again.")
    stock = owned_parts.snapshot()
    if not stock["lots"]:
        raise HTTPException(422, "Add usable inventory in My Parts first")
    if _fit_lock.locked():
        raise HTTPException(
            429, "Another model is being fitted. Try again when it finishes."
        )
    async with _fit_lock:
        store = get_store()
        chat = store.create_chat()
        store.update_chat(
            chat["id"],
            title="Use my parts: " + source.stem,
            options={"use_my_parts": True},
        )
        ctx = tools.ToolContext(chat["id"], store, lambda *_: None)
        ctx.work_dir.mkdir(parents=True, exist_ok=True)
        owned_parts.capture(store, chat["id"])
        model = ctx.work_dir / ("fit-" + uuid.uuid4().hex[:12] + ".mpd")
        model.write_bytes(source_bytes)
        sandbox.give_to_agent(model)
        store.add_message(
            chat["id"],
            {
                "role": "user",
                "content": "Fit "
                + source.name
                + " to my saved inventory. Preserve the original and report missing parts.",
            },
        )
        try:
            published = await tools.t_publish_model(
                ctx, "output/" + model.name, source.stem + " my parts"
            )
        except tools.ToolError as exc:
            raise HTTPException(422, str(exc)) from None
        if not published.models:
            raise HTTPException(
                422, "Fitting or validation failed. Your original is unchanged."
            )
        report = json.loads((ctx.work_dir / "owned-parts-report.json").read_text())
        target = store.resolve(chat["id"], published.models[0]["model"])
        store.add_message(
            chat["id"],
            {
                "role": "assistant",
                "content": f"Saved a fitted version: {report['matched_parts']} of {report['total_parts']} pieces available, {report['missing_parts']} missing. {report['color_changes']} color changes and {report['splits']} brick/plate splits.",
                "_models": [published.models[0]["id"]],
            },
        )
        return {"model": model_info(target), "chat_id": chat["id"], "report": report}


@router.get("/revision")
def revision(file: str):
    import hashlib

    if len(file) > 160:
        raise HTTPException(422, "Model filename exceeds 160 characters")
    source = settings.GENERATED_DIR / file
    if (
        Path(file).name != file
        or source.is_symlink()
        or not source.is_file()
        or source.suffix.lower() not in (".mpd", ".ldr")
    ):
        raise HTTPException(404, "Choose a saved model from My Models")
    if source.stat().st_size > 32 * 1024 * 1024:
        raise HTTPException(413, "Model exceeds 32 MB")
    return {"revision": hashlib.sha256(source.read_bytes()).hexdigest()}
