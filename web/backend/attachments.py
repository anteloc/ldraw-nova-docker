"""Bounded image and document inputs. Never fetch arbitrary attachment URLs."""
import base64
import binascii
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import sandbox
from paths import safe_join

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 12 * 1024 * 1024
DOCUMENT_SUFFIXES = {".pdf", ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ".html",
                     ".rtf", ".docx", ".xlsx", ".pptx", ".mpd", ".ldr", ".dat"}


@dataclass
class Document:
    name: str
    data: bytes


def validate_documents(documents: list[dict], images: list[str] = ()) -> list[Document]:
    if len(documents) > 4:
        raise ValueError("Attach at most four documents")
    result = []
    total = sum(len(base64.b64decode(url.split(",", 1)[1])) for url in images)
    for item in documents:
        name, encoded = item.get("name"), item.get("data")
        if (not isinstance(name, str) or not name or len(name.encode("utf-8")) > 255
                or name.startswith(".") or any(c in name for c in "/\\") or any(ord(c) < 32 for c in name)):
            raise ValueError("Use a document filename without folders or control characters")
        if Path(name).suffix.lower() not in DOCUMENT_SUFFIXES:
            raise ValueError("Choose a PDF, text, Office or LDraw document. Use the image button for images.")
        if not isinstance(encoded, str) or len(encoded) > MAX_DOCUMENT_BYTES * 4 // 3 + 200:
            raise ValueError("Each document must be at most 5 MB")
        match = re.fullmatch(r"data:[^,;]*;base64,([A-Za-z0-9+/=]*)", encoded)
        if not match:
            raise ValueError("Invalid document encoding")
        try:
            data = base64.b64decode(match[1], validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Invalid document encoding") from None
        if len(data) > MAX_DOCUMENT_BYTES:
            raise ValueError("Each document must be at most 5 MB")
        if data.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF87a", b"GIF89a")) or data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            raise ValueError("Use the image button for images")
        total += len(data)
        result.append(Document(name, data))
    if total > MAX_ATTACHMENT_BYTES:
        raise ValueError("Images and documents must total at most 12 MB")
    return result


def save_documents(store, chat_id: str, documents: list[Document]) -> list[dict]:
    """Separate upload directories preserve filenames without overwriting previous uploads."""
    if not documents:
        return []
    folder = safe_join(store.work_dir(chat_id), "uploads/" + uuid.uuid4().hex)
    if folder is None:
        raise ValueError("The uploads folder must stay inside this chat's workspace")
    folder.mkdir(parents=True)
    sandbox.give_to_agent(folder.parent)
    sandbox.give_to_agent(folder)
    saved = []
    try:
        for index, document in enumerate(documents):
            target = folder / str(index) / document.name
            target.parent.mkdir()
            sandbox.give_to_agent(target.parent)
            target.write_bytes(document.data)
            saved.append({"name": document.name, "size": len(document.data), "path": store.ref(chat_id, target)})
    except Exception:
        import shutil
        shutil.rmtree(folder)
        raise
    return saved


def validate_images(images: list[str]) -> list[str]:
    if len(images) > 4:
        raise ValueError("Attach at most four images")
    total = 0
    for url in images:
        if len(url) > MAX_IMAGE_BYTES * 4 // 3 + 100:
            raise ValueError("Each image must be at most 5 MB")
        match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", url)
        if not match:
            raise ValueError("Images must be PNG, JPEG or WebP data URLs")
        try:
            data = base64.b64decode(match[2], validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Invalid image encoding") from None
        valid = {"png": data.startswith(b"\x89PNG\r\n\x1a\n"), "jpeg": data.startswith(b"\xff\xd8\xff"),
                 "webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP"}
        if not valid[match[1]] or len(data) > MAX_IMAGE_BYTES:
            raise ValueError("Invalid image or image exceeds 5 MB")
        total += len(data)
    if total > 12 * 1024 * 1024:
        raise ValueError("Images must total at most 12 MB")
    return images
