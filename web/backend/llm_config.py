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
import os
import threading
import uuid
from typing import Any, Optional

import settings
import model_catalog

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
    return MASK_PREFIX + value[-4:] if len(value) > 8 else MASK_PREFIX


def public(entry: dict) -> dict:
    """An entry as the UI may see it: secrets masked, capabilities resolved."""
    params = mask_secrets(entry["litellm_params"])
    return {**entry, "litellm_params": params, "resolved_capabilities": capabilities(entry),
            "profile": model_catalog.profile(entry["litellm_params"]["model"])}


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
    if isinstance(value, str) and value.startswith(MASK_PREFIX):
        if previous is None:
            raise ValueError("Masked credentials cannot be imported. Enter a key or environment reference.")
        return previous
    return value


def list_entries() -> tuple[list[dict], Optional[str]]:
    data = _load()
    return data["models"], data["default_id"]


def get(entry_id: str) -> Optional[dict]:
    return next((m for m in _load()["models"] if m["id"] == entry_id), None)


def _clean(entry: dict, previous: Optional[dict]) -> dict:
    params = restore_secrets(dict(entry.get("litellm_params") or {}), (previous or {}).get("litellm_params"))
    if not str(params.get("model", "")).strip():
        raise ValueError("litellm_params.model is required, e.g. 'anthropic/claude-sonnet-5'")
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
    return {
        "id": (previous or {}).get("id") or uuid.uuid4().hex[:12],
        "model_name": (entry.get("model_name") or params["model"]).strip(),
        "litellm_params": params,
        "capabilities": {k: caps[k] for k in ("tools", "vision")},
        "auth_mode": auth_mode,
    }


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
    return [create({"model_name": m.get("model_name"), "litellm_params": m.get("litellm_params", {}),
                    "capabilities": m.get("capabilities"), "auth_mode": m.get("auth_mode")}) for m in model_list]


def resolve_params(entry: dict) -> dict:
    """litellm_params with os.environ/NAME references resolved."""
    resolved = {}
    for k, v in entry["litellm_params"].items():
        if isinstance(v, str) and v.startswith("os.environ/"):
            env_name = v.split("/", 1)[1]
            if env_name not in os.environ:
                raise ValueError(f"{k} refers to environment variable {env_name}, which is not set")
            v = os.environ[env_name]
        resolved[k] = v
    return resolved


def capabilities(entry: dict) -> dict[str, Optional[bool]]:
    """True/False when known (configured, or LiteLLM's model map knows), None when unknown."""
    import litellm

    model = entry["litellm_params"]["model"]
    spec = model_catalog.profile(model)
    try:
        litellm.get_model_info(model)
        known = True
    except Exception:  # noqa: BLE001 - not in LiteLLM's model map (Ollama, custom servers, new models)
        known = False
    checks = {"tools": litellm.supports_function_calling, "vision": litellm.supports_vision}
    result = {}
    for cap, check in checks.items():
        configured = entry.get("capabilities", {}).get(cap, "auto")
        if isinstance(configured, bool):
            result[cap] = configured
        elif cap in spec:
            result[cap] = spec[cap]
        elif not known:
            result[cap] = None       # LiteLLM would answer False for anything it doesn't know
        else:
            try:
                result[cap] = bool(check(model=model))
            except Exception:  # noqa: BLE001
                result[cap] = None
    return result
