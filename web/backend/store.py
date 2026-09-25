"""Chat history in SQLite (/config/chats.sqlite, next to the LLM settings).

Messages are stored in OpenAI chat format — LiteLLM's canonical format — so a
chat can be continued with any configured model. Keys starting with "_" are
our own metadata (artifacts, images, UI-only notes) and are stripped before a
message is sent to an LLM (see agent.llm_history).
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    llm_model_id TEXT,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    data       TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_chat ON messages(chat_id, id);
CREATE TABLE IF NOT EXISTS artifacts (
    id          TEXT PRIMARY KEY,
    chat_id     TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    model_path  TEXT NOT NULL,   -- relative to DATA_DIR
    image_path  TEXT,            -- relative to DATA_DIR; NULL if the render failed
    warnings    TEXT NOT NULL,   -- JSON list
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS artifacts_chat ON artifacts(chat_id, created_at);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        # Default rollback journal, not WAL: WAL's shared-memory file is
        # unreliable on Docker Desktop bind mounts, and there's one writer anyway.
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()

    def _q(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, params).fetchall()

    def _x(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            return self._db.execute(sql, params).lastrowid

    # --- chats -------------------------------------------------------------

    def create_chat(self, title: str = "New chat", llm_model_id: Optional[str] = None) -> dict:
        now = time.time()
        chat_id = uuid.uuid4().hex[:12]
        self._x("INSERT INTO chats VALUES (?, ?, ?, ?, ?)", (chat_id, title, llm_model_id, now, now))
        return self.get_chat(chat_id)

    def get_chat(self, chat_id: str) -> Optional[dict]:
        rows = self._q("SELECT * FROM chats WHERE id = ?", (chat_id,))
        return dict(rows[0]) if rows else None

    def list_chats(self) -> list[dict]:
        chats = [dict(r) for r in self._q("SELECT * FROM chats ORDER BY updated_at DESC")]
        by_chat: dict[str, list[dict]] = {}
        for a in self.list_artifacts():
            by_chat.setdefault(a["chat_id"], []).append(a)
        for chat in chats:
            chat["artifacts"] = by_chat.get(chat["id"], [])
        return chats

    def update_chat(self, chat_id: str, **fields: Any) -> None:
        allowed = {k: v for k, v in fields.items() if k in ("title", "llm_model_id")}
        allowed["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in allowed)
        self._x(f"UPDATE chats SET {cols} WHERE id = ?", (*allowed.values(), chat_id))

    def delete_chat(self, chat_id: str) -> None:
        self._x("DELETE FROM chats WHERE id = ?", (chat_id,))

    # --- messages ----------------------------------------------------------

    def add_message(self, chat_id: str, message: dict) -> int:
        now = time.time()
        msg_id = self._x(
            "INSERT INTO messages (chat_id, data, created_at) VALUES (?, ?, ?)",
            (chat_id, json.dumps(message), now),
        )
        self._x("UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id))
        return msg_id

    def messages(self, chat_id: str) -> list[dict]:
        rows = self._q("SELECT id, data, created_at FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,))
        return [{"id": r["id"], "created_at": r["created_at"], **json.loads(r["data"])} for r in rows]

    # --- artifacts (generated models) --------------------------------------

    def add_artifact(self, chat_id: str, name: str, model_path: str,
                     image_path: Optional[str], warnings: list[str]) -> dict:
        art_id = uuid.uuid4().hex[:12]
        self._x(
            "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?)",
            (art_id, chat_id, name, model_path, image_path, json.dumps(warnings), time.time()),
        )
        return self.get_artifact(art_id)

    def get_artifact(self, art_id: str) -> Optional[dict]:
        rows = self._q("SELECT * FROM artifacts WHERE id = ?", (art_id,))
        return _artifact(rows[0]) if rows else None

    def list_artifacts(self, chat_id: Optional[str] = None, limit: int = 1000) -> list[dict]:
        if chat_id:
            rows = self._q("SELECT * FROM artifacts WHERE chat_id = ? ORDER BY created_at LIMIT ?", (chat_id, limit))
        else:
            rows = self._q(
                "SELECT a.*, c.title AS chat_title FROM artifacts a JOIN chats c ON c.id = a.chat_id "
                "ORDER BY a.created_at DESC LIMIT ?", (limit,))
        return [_artifact(r) for r in rows]


def _artifact(row: sqlite3.Row) -> dict:
    a = dict(row)
    a["warnings"] = json.loads(a["warnings"])
    return a


_store: Optional[Store] = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store(settings.DB_PATH)
    return _store
