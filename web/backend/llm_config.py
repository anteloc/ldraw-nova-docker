"""LLM model entries, in LiteLLM's own proxy `model_list` shape:

    {"id": "...", "model_name": "Claude Sonnet 5",
     "litellm_params": {"model": "anthropic/claude-sonnet-5", "api_key": "...", ...},
     "capabilities": {"tools": "auto", "vision": "auto"}}

`litellm_params` is passed verbatim to litellm.acompletion(), so anything
LiteLLM accepts works (api_base, api_version, aws_region_name, vertex_project,
extra_headers, ...). A value of "os.environ/NAME" is read from the
environment at call time, as in LiteLLM's proxy config.

Stored in CONFIG_DIR/models.json (0600) — never under /data, which agents
can write to and the host can read.
"""
from __future__ import annotations

import json
import hashlib
import os
import threading
import time
import uuid
from typing import Any, Optional

import settings
import model_catalog
import environment_config

SECRET_MARKERS = ("key", "secret", "token", "password", "credential")
MASK_PREFIX = "••••"
_lock = threading.Lock()


def _path():
    return settings.CONFIG_DIR / "models.json"


def _load() -> dict:
    try:
        data = json.loads(_path().read_text())
    except FileNotFoundError:
        data = {}
    data.setdefault("models", [])
    data.setdefault("default_id", None)
    for entry in data["models"]:
        params = entry.get("litellm_params", {})
        if params.get("api_key") == "os.environ/OPENROUTER_LDRAW_ASTRA_API_KEY":
            params["api_key"] = "os.environ/OPENROUTER_API_KEY"
    return data


def _save(data: dict) -> None:
    settings.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(settings.CONFIG_DIR, 0o700)
    tmp = _path().with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, _path())


def is_secret(name: str) -> bool:
    return any(marker in name.lower() for marker in SECRET_MARKERS)


def _mask(value: Any) -> Any:
    if not isinstance(value, str) or not value or value.startswith("os.environ/"):
        return value
    return MASK_PREFIX


def public(entry: dict) -> dict:
    """An entry as the UI may see it: secrets masked, capabilities resolved."""
    params = mask_secrets(entry["litellm_params"])
    return {**{k: v for k, v in entry.items() if k != "_connection_test"},
            "connection_status": connection_status(entry),
            "litellm_params": params, "resolved_capabilities": capabilities(entry),
            "profile": model_catalog.entry_profile(entry)}


def connection_fingerprint(entry: dict) -> str:
    """Bind test results to the exact saved settings and referenced credentials."""
    environment = environment_config.snapshot()
    def effective(value):
        if isinstance(value, dict):
            return {k: effective(v) for k, v in value.items()}
        if isinstance(value, list):
            return [effective(v) for v in value]
        if isinstance(value, str) and value.startswith("os.environ/"):
            return environment.get(value.split("/", 1)[1])
        return value
    params = effective(entry["litellm_params"])
    provider = params.get("model", "").split("/")[0]
    default_key = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY"}.get(provider)
    if not params.get("api_key") and entry.get("auth_mode") != "browser" and default_key:
        params["api_key"] = environment.get(default_key)
    value = {"params": params, "auth": entry.get("auth_mode"), "name": entry.get("model_name")}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def connection_status(entry: dict) -> str:
    test = entry.get("_connection_test") or {}
    if test.get("fingerprint") != connection_fingerprint(entry):
        return "not_tested"
    return "connected" if test.get("ok") else "not_connected"


def record_connection_test(entry_id: str, fingerprint: str, ok: bool) -> str:
    with _lock:
        data = _load()
        entry = next((m for m in data["models"] if m["id"] == entry_id), None)
        if entry is None or connection_fingerprint(entry) != fingerprint:
            return "not_tested"  # credentials changed while the test was in flight
        entry["_connection_test"] = {"fingerprint": fingerprint, "ok": ok, "checked_at": time.time()}
        _save(data)
        return connection_status(entry)


def mask_secrets(value, secret=False):
    if isinstance(value, dict):
        return {k: mask_secrets(v, secret or is_secret(k) or k.lower() in ("authorization", "extra_headers")) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_secrets(v, secret) for v in value]
    return _mask(value) if secret else value


def restore_secrets(value, previous):
    if isinstance(value, dict):
        old = previous if isinstance(previous, dict) else {}
        return {k: restore_secrets(v, old.get(k)) for k, v in value.items()}
    if isinstance(value, list):
        old = previous if isinstance(previous, list) else []
        return [restore_secrets(v, old[i] if i < len(old) else None) for i, v in enumerate(value)]
    if isinstance(value, str) and value.startswith(MASK_PREFIX):
        if previous is None:
            raise ValueError("Masked credentials cannot be imported. Enter a key or environment reference.")
        return previous
    return value


def list_entries() -> tuple[list[dict], Optional[str]]:
    data = _load()
    return data["models"], data["default_id"]


def builder_entries() -> tuple[list[dict], Optional[str]]:
    entries, default = list_entries()
    entries = [e for e in entries if model_catalog.builder_supported(e["litellm_params"]["model"])]
    return entries, default if any(e["id"] == default for e in entries) else (entries[0]["id"] if entries else None)


def get(entry_id: str) -> Optional[dict]:
    return next((m for m in _load()["models"] if m["id"] == entry_id), None)


def _clean(entry: dict, previous: Optional[dict]) -> dict:
    params = restore_secrets(dict(entry.get("litellm_params") or {}), (previous or {}).get("litellm_params"))
    if not str(params.get("model", "")).strip():
        raise ValueError("litellm_params.model is required, e.g. 'anthropic/claude-sonnet-5'")
    params["model"] = params["model"].strip()
    if params.get("api_key") == "os.environ/OPENROUTER_LDRAW_ASTRA_API_KEY":
        params["api_key"] = "os.environ/OPENROUTER_API_KEY"
    if params["model"] == "openrouter/":
        raise ValueError("Choose an OpenRouter model, e.g. openrouter/openai/gpt-6-luna")
    old = (previous or {}).get("litellm_params", {})
    for k, v in list(params.items()):
        if v is None or v == "":
            params.pop(k)
        elif is_secret(k) and isinstance(v, str) and v.startswith(MASK_PREFIX):
            # The UI sent back the masked value: keep the stored secret.
            if k in old:
                params[k] = old[k]
            else:
                params.pop(k)
    caps = {"tools": "auto", "vision": "auto", **(entry.get("capabilities") or {})}
    auth_mode = entry.get("auth_mode") or "api_key"
    if params["model"].startswith("chatgpt/"):
        auth_mode = "browser"
    if auth_mode not in ("api_key", "browser"):
        raise ValueError("Unknown authentication method")
    if auth_mode == "browser":
        if params["model"].split("/", 1)[0] not in ("openai", "anthropic", "chatgpt"):
            raise ValueError("Browser login is supported for OpenAI and Anthropic")
        params = {"model": params["model"]}
    for cap in ("tools", "vision"):
        if caps[cap] not in (True, False, "auto"):
            raise ValueError("Capabilities must be true, false or auto")
    if not model_catalog.builder_supported(params["model"]):
        raise ValueError("Choose a model with verified tool calling and image input support")
    cleaned = {
        "id": (previous or {}).get("id") or uuid.uuid4().hex[:12],
        "model_name": (entry.get("model_name") or params["model"]).strip(),
        "litellm_params": params,
        "capabilities": {"tools": "auto", "vision": "auto"},
        "auth_mode": auth_mode,
    }
    if previous and all(cleaned[k] == previous.get(k) for k in cleaned):
        if previous.get("_connection_test"):
            cleaned["_connection_test"] = previous["_connection_test"]
    return cleaned


def create(entry: dict) -> dict:
    with _lock:
        data = _load()
        new = _clean(entry, None)
        data["models"].append(new)
        if not data["default_id"]:
            data["default_id"] = new["id"]
        _save(data)
        return new


def update(entry_id: str, entry: dict) -> Optional[dict]:
    with _lock:
        data = _load()
        for i, m in enumerate(data["models"]):
            if m["id"] == entry_id:
                data["models"][i] = _clean(entry, m)
                _save(data)
                return data["models"][i]
        return None


def delete(entry_id: str) -> bool:
    with _lock:
        data = _load()
        before = len(data["models"])
        data["models"] = [m for m in data["models"] if m["id"] != entry_id]
        if data["default_id"] == entry_id:
            data["default_id"] = data["models"][0]["id"] if data["models"] else None
        _save(data)
        return len(data["models"]) < before


def set_default(entry_id: str) -> None:
    with _lock:
        data = _load()
        if any(m["id"] == entry_id for m in data["models"]):
            data["default_id"] = entry_id
            _save(data)


def import_model_list(model_list: list[dict]) -> list[dict]:
    """Import LiteLLM proxy-style entries ({model_name, litellm_params})."""
    if not isinstance(model_list, list) or any(not isinstance(m, dict) for m in model_list):
        raise ValueError("model_list must be a list of models")
    with _lock:
        # Validate the entire batch first; one unsupported model must not leave
        # a half-imported list or duplicate entries on the user's next attempt.
        imported = [_clean(m, None) for m in model_list]
        data = _load()
        data["models"].extend(imported)
        if not data["default_id"] and imported:
            data["default_id"] = imported[0]["id"]
        _save(data)
        return imported


def resolve_params(entry: dict) -> dict:
    """Resolve references, including nested params, with saved overrides first."""
    environment = environment_config.snapshot()

    def resolve(value):
        if isinstance(value, dict):
            return {k: resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [resolve(v) for v in value]
        if isinstance(value, str) and value.startswith("os.environ/"):
            name = value.split("/", 1)[1]
            if name == "OPENROUTER_LDRAW_ASTRA_API_KEY":
                name = "OPENROUTER_API_KEY"
            if not environment.get(name, "").strip():
                raise ValueError(f"Environment variable {name} is not set or is empty")
            return environment[name]
        return value

    return resolve(entry["litellm_params"])


def capabilities(entry: dict) -> dict[str, bool]:
    """Only advertise capabilities verified by the model catalog/provider metadata."""
    spec = model_catalog.profile(entry["litellm_params"]["model"])
    return {"tools": spec["tools"], "vision": spec["vision"]}
