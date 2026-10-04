"""Builder presets and published capabilities; no network work on UI reads.

The bundled snapshot has per-model sources and verification dates. Test refreshes
provider metadata when available, without mistaking a successful text response
for proof of vision, tool use, or a particular context limit.
"""
import copy
import json
import math
from pathlib import Path

import litellm

EFFORTS = ["low", "medium", "high", "xhigh", "max"]
_PROFILES = json.loads(Path(__file__).with_name("model_catalog_data.json").read_text())
CATALOG = [entry for entry in _PROFILES if entry["preset"]]
OPENROUTER_CATALOG = [entry for entry in CATALOG if entry["model"].startswith("openrouter/")]


def profile(model: str) -> dict:
    canonical = model.replace("chatgpt/", "openai/", 1).replace("responses/", "")
    known = next((m for m in _PROFILES if m["model"] == canonical), None)
    if known:
        return {**copy.deepcopy(known), "context_budgets": [known["context_window"]]}
    try:
        info = litellm.get_model_info(model)
    except Exception:
        info = {}
    window = info.get("max_input_tokens") or None
    def support(key):
        return info.get(key) if isinstance(info.get(key), bool) else None
    def rate(key):
        value = info.get(key)
        return round(value * 1_000_000, 8) if isinstance(value, (float, int)) and math.isfinite(value) and value >= 0 else None
    return {"model": model, "name": model, "context_window": window,
            "max_output_tokens": info.get("max_output_tokens"),
            "context_budgets": [window] if window else [], "default_effort": None,
            "tools": support("supports_function_calling"), "vision": support("supports_vision"),
            "reasoning": support("supports_reasoning"), "efforts": [],
            "pricing": {"input": rate("input_cost_per_token"), "output": rate("output_cost_per_token"), "currency": "USD"} if info else None,
            "source_label": "LiteLLM catalogue" if info else None,
            "source_url": None, "verified_at": None}


def builder_supported(model: str) -> bool:
    spec = profile(model)
    return spec["tools"] is True and spec["vision"] is True


def entry_profile(entry: dict) -> dict:
    params = entry["litellm_params"]
    spec = profile(params["model"])
    metadata = (entry.get("_connection_test") or {}).get("metadata")
    if metadata:
        spec.update(copy.deepcopy(metadata))
    extra = params.get("extra_body") or {}
    configured = (extra.get("reasoning", {}).get("effort") or params.get("reasoning_effort")
                  or params.get("output_config", {}).get("effort"))
    if configured in spec["efforts"]:
        spec["default_effort"] = configured
    return spec


def validate_options(entry: dict, options: dict | None) -> dict:
    value = {"mode": "agent", "permissions": "ask", "effort": None, "context_tokens": None, **(options or {})}
    if value["mode"] not in ("plan", "agent"):
        raise ValueError("Unknown mode")
    if value["permissions"] not in ("ask", "full", "read_only"):
        raise ValueError("Unknown permission setting")
    if type(value.get("use_my_parts", False)) is not bool:
        raise ValueError("Use my parts must be a checkbox value")
    spec = entry_profile(entry)
    if value["effort"] is None:
        value["effort"] = spec["default_effort"]
    if value["context_tokens"] is None:
        value["context_tokens"] = spec["context_window"]
    if value["effort"] and value["effort"] not in spec["efforts"]:
        raise ValueError("This effort is not supported by the selected model")
    if value["context_tokens"] is not None and value["context_tokens"] not in spec["context_budgets"]:
        raise ValueError("This context budget is not supported by the selected model")
    return value
