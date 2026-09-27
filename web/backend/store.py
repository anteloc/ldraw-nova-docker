"""Chat history as plain files, one folder per chat:

    data/chats/<chat-id>/
        chat.json        {"id", "title", "llm_model_id", "created_at", "updated_at"}
        messages.jsonl   one message per line: OpenAI chat format (LiteLLM's canonical
                         format, so any model can continue the chat) plus our own
                         "_"-prefixed metadata, stripped before sending (agent.llm_history)
        models.jsonl     models the chat produced, as references into data/generated:
                         {"id", "name", "model": "../../generated/red-car-v1.mpd", ...}
        renders/         extra renders the agent showed in the chat
    data/output/<chat-id>/   the chat's agent work folder, created alongside

Paths stored inside a chat folder are relative to that folder, so data/ can be
moved or copied as a whole.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Optional

import settings

CHAT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class ChatStore:
    def __init__(self, chats_dir: Path, output_dir: Path):
        self.chats_dir = chats_dir
        self.output_dir = output_dir
        self._lock = threading.RLock()
        self._next_id: dict[str, int] = {}

    # --- paths -------------------------------------------------------------

    @staticmethod
    def valid_id(chat_id: str) -> bool:
        return bool(CHAT_ID_RE.match(chat_id or ""))

    def chat_dir(self, chat_id: str) -> Path:
        if not self.valid_id(chat_id):
            raise ValueError(f"invalid chat id {chat_id!r}")
        return self.chats_dir / chat_id

    def work_dir(self, chat_id: str) -> Path:
        """The chat's agent work folder: data/output/<chat-id>/."""
        if not self.valid_id(chat_id):
            raise ValueError(f"invalid chat id {chat_id!r}")
        return self.output_dir / chat_id

    def resolve(self, chat_id: str, ref: str) -> Path:
        """A path stored in a chat's files (relative to its folder) -> absolute path."""
        return Path(os.path.normpath(self.chat_dir(chat_id) / ref))

    def ref(self, chat_id: str, path: Path) -> str:
        """An absolute path -> a reference relative to the chat's folder."""
        return Path(os.path.relpath(path, self.chat_dir(chat_id))).as_posix()

    # --- chats -------------------------------------------------------------

    def create_chat(self, title: str = "New chat", llm_model_id: Optional[str] = None) -> dict:
        with self._lock:
            chat_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
            now = time.time()
            self.chat_dir(chat_id).mkdir(parents=True)
            self.work_dir(chat_id).mkdir(parents=True, exist_ok=True)
            chat = {"id": chat_id, "title": title, "llm_model_id": llm_model_id,
                    "created_at": now, "updated_at": now}
            self._write_chat(chat)
            return chat

    def get_chat(self, chat_id: str) -> Optional[dict]:
        if not self.valid_id(chat_id):
            return None
        try:
            return json.loads((self.chat_dir(chat_id) / "chat.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def list_chats(self) -> list[dict]:
        if not self.chats_dir.is_dir():
            return []
        chats = [c for c in (self.get_chat(p.name) for p in self.chats_dir.iterdir() if p.is_dir()) if c]
        return sorted(chats, key=lambda c: c["updated_at"], reverse=True)

    def update_chat(self, chat_id: str, **fields: Any) -> None:
        with self._lock:
            chat = self.get_chat(chat_id)
            if chat is None:
                return
            chat.update({k: v for k, v in fields.items() if k in ("title", "llm_model_id", "options")})
            chat["updated_at"] = time.time()
            self._write_chat(chat)

    def delete_chat(self, chat_id: str) -> None:
        """Removes the chat folder and its work folder. Its models stay in data/generated."""
        with self._lock:
            shutil.rmtree(self.chat_dir(chat_id), ignore_errors=True)
            shutil.rmtree(self.work_dir(chat_id), ignore_errors=True)
            self._next_id.pop(chat_id, None)

    def _write_chat(self, chat: dict) -> None:
        path = self.chat_dir(chat["id"]) / "chat.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(chat, indent=2))
        os.replace(tmp, path)

    # --- messages ----------------------------------------------------------

    def add_message(self, chat_id: str, message: dict) -> int:
        with self._lock:
            if chat_id not in self._next_id:
                self._next_id[chat_id] = max((m["id"] for m in self.messages(chat_id)), default=0) + 1
            msg_id = self._next_id[chat_id]
            self._next_id[chat_id] += 1
            record = {"id": msg_id, "created_at": time.time(), **message}
            self._append(chat_id, "messages.jsonl", record)
            self.update_chat(chat_id)
            return msg_id

    def messages(self, chat_id: str) -> list[dict]:
        return self._read(chat_id, "messages.jsonl")

    # --- models the chat produced (references into data/generated) ---------

    def add_model(self, chat_id: str, name: str, model_path: Path, warnings: list[str]) -> dict:
        record = {"id": secrets.token_hex(6), "name": name, "model": self.ref(chat_id, model_path),
                  "warnings": warnings, "created_at": time.time()}
        with self._lock:
            self._append(chat_id, "models.jsonl", record)
        return record

    def models(self, chat_id: str) -> list[dict]:
        return self._read(chat_id, "models.jsonl")

    # --- jsonl helpers -----------------------------------------------------

    def _append(self, chat_id: str, name: str, record: dict) -> None:
        with (self.chat_dir(chat_id) / name).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read(self, chat_id: str, name: str) -> list[dict]:
        path = self.chat_dir(chat_id) / name
        if not path.exists():
            return []
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue                     # e.g. a line cut short by a crash
        return records


_store: Optional[ChatStore] = None


def get_store() -> ChatStore:
    global _store
    if _store is None:
        _store = ChatStore(settings.CHATS_DIR, settings.OUTPUT_DIR)
    return _store
