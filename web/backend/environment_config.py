"""Private, persistent overrides for the backend's inherited environment."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import uuid
from pathlib import Path

# Locate the override file before applying it, so an override cannot relocate
# its own storage. Import this module before settings and provider libraries.
_directory = Path(os.environ.get("LDRAW_ASTRA_WEB_CONFIG_DIR", "/config"))
_lock = threading.RLock()
_rows: list[dict] = []
_inherited: dict[str, str | None] = {}
_initialized = False


def _clean(rows: list, previous: list) -> list[dict]:
    if not isinstance(rows, list) or len(rows) > 256:
        raise ValueError("Provide at most 256 environment variables")
    # Read older installations using the new standard name without losing their
    # saved value. An explicitly configured standard name wins if both exist.
    if not any(isinstance(row, dict) and row.get("name") == "OPENROUTER_API_KEY" for row in rows):
        rows = [{**row, "name": "OPENROUTER_API_KEY"} if isinstance(row, dict) and row.get("name") == "OPENROUTER_LDRAW_ASTRA_API_KEY" else row for row in rows]
    old = {row["id"]: row for row in previous}
    names, ids, result = set(), set(), []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each environment variable needs a name and value")
        name = row.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,254}", name.strip()):
            raise ValueError("Variable names must start with a letter or underscore and contain only letters, digits or underscores")
        name = name.strip()
        if name in names:
            raise ValueError("Each environment variable name must be unique")
        row_id = row.get("id")
        if row_id is not None and (not isinstance(row_id, str) or row_id not in old or row_id in ids):
            raise ValueError("An environment variable changed elsewhere. Reload Settings and try again.")
        value = row.get("value")
        if value is None and row_id in old:
            value = old[row_id]["value"]  # unchanged private value, also on rename
        if not isinstance(value, str) or "\0" in value or len(value) > 65_536:
            raise ValueError("Variable values must be text of at most 65,536 characters without null bytes")
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise ValueError("Variable values must be valid UTF-8 text") from None
        row_id = row_id or uuid.uuid4().hex
        names.add(name)
        ids.add(row_id)
        result.append({"id": row_id, "name": name, "value": value})
    return result


def _apply(rows: list[dict]) -> None:
    global _rows
    names = {row["name"] for row in rows}
    for name in list(_inherited):
        if name not in names:
            value = _inherited.pop(name)
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    for row in rows:
        name = row["name"]
        if name not in _inherited:
            _inherited[name] = os.environ.get(name)
        os.environ[name] = row["value"]
    _rows = rows


def initialize() -> None:
    global _initialized
    with _lock:
        if _initialized:
            return
        try:
            data = json.loads((_directory / "environment.json").read_text())
            rows = _clean(data["variables"], data["variables"])
        except FileNotFoundError:
            rows = []
        except (ValueError, KeyError, TypeError):
            # Never include file contents or values in startup errors.
            raise RuntimeError("Cannot load saved environment variables") from None
        _apply(rows)
        _initialized = True


def public() -> list[dict]:
    """Settings explicitly exposes editable values; null still preserves a value."""
    initialize()
    with _lock:
        return [{**row, "has_value": bool(row["value"])} for row in _rows]


def save(rows: list) -> list[dict]:
    initialize()
    with _lock:
        cleaned = _clean(rows, _rows)
        _directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        _directory.chmod(0o700)
        fd, tmp = tempfile.mkstemp(prefix=".environment-", suffix=".tmp", dir=_directory)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump({"variables": cleaned}, stream, indent=2)
            os.replace(tmp, _directory / "environment.json")
        finally:
            Path(tmp).unlink(missing_ok=True)
        _apply(cleaned)
        return public()


def snapshot() -> dict[str, str]:
    initialize()
    with _lock:
        # Explicit references retain saved precedence even if another library
        # has subsequently changed a process environment variable.
        env = {**os.environ, **{row["name"]: row["value"] for row in _rows}}
        if "OPENROUTER_API_KEY" not in env and "OPENROUTER_LDRAW_ASTRA_API_KEY" in env:
            env["OPENROUTER_API_KEY"] = env["OPENROUTER_LDRAW_ASTRA_API_KEY"]
        return env
