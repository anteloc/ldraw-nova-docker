"""Verified builder models and their actual context windows and effort defaults.

Defaults checked 2026-09-29 against OpenRouter's /api/v1/models, OpenAI's
model docs and https://platform.claude.com/docs/en/build-with-claude/effort.
OpenRouter currently advertises high for Opus 5.5; Anthropic defaults to medium.
"""
import litellm

EFFORTS = ["low", "medium", "high", "xhigh", "max"]
CATALOG = [
    {"model": "openai/gpt-6-astra", "name": "GPT-6 Astra", "context_window": 1_050_000, "efforts": EFFORTS},
    {"model": "openai/gpt-6-sol", "name": "GPT-6 Sol", "context_window": 1_050_000, "efforts": ["none", *EFFORTS]},
    {"model": "openai/gpt-6-luna", "name": "GPT-6 Luna", "context_window": 1_050_000, "efforts": ["none", *EFFORTS]},
    {"model": "openai/gpt-5.6-terra", "name": "GPT-5.6 Terra", "context_window": 1_050_000, "efforts": ["none", *EFFORTS]},
    {"model": "anthropic/claude-opus-5-5", "name": "Claude Opus 5.5", "context_window": 1_000_000, "efforts": EFFORTS},
    {"model": "anthropic/claude-opus-5", "name": "Claude Opus 5", "context_window": 1_000_000, "efforts": EFFORTS},
    {"model": "anthropic/claude-sonnet-5", "name": "Claude Sonnet 5", "context_window": 1_000_000, "efforts": EFFORTS},
    {"model": "anthropic/claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5 (latest released Haiku)", "context_window": 200_000, "efforts": []},
]
for entry in CATALOG:
    entry["default_effort"] = (None if not entry["efforts"] else
                               "medium" if entry["model"].startswith("openai/") or entry["model"] == "anthropic/claude-opus-5-5" else "high")

# OpenRouter slugs, capabilities, context and reasoning.supported_efforts
# checked against https://openrouter.ai/api/v1/models on 2026-09-27.
_OPENROUTER_SLUGS = {
    "anthropic/claude-opus-5-5": "anthropic/claude-opus-5.5",
    "anthropic/claude-haiku-4-5-20251001": "anthropic/claude-haiku-4.5",
}
OPENROUTER_CATALOG = [
    {**entry, "model": "openrouter/" + _OPENROUTER_SLUGS.get(entry["model"], entry["model"]),
     "name": entry["name"].replace(" (latest released Haiku)", "") + " (OpenRouter)",
     "default_effort": "high" if entry["model"] == "anthropic/claude-opus-5-5" else entry["default_effort"]}
    for entry in CATALOG
]
CATALOG += OPENROUTER_CATALOG


def profile(model: str) -> dict:
    canonical = model.replace("chatgpt/", "openai/", 1).replace("responses/", "")
    known = next((m for m in CATALOG if m["model"] == canonical), None)
    if known:
        return {**known, "tools": True, "vision": True,
                "context_budgets": [known["context_window"]]}
    try:
        info = litellm.get_model_info(model)
    except Exception:
        info = {}
    window = info.get("max_input_tokens")
    return {"model": model, "name": model, "context_window": window,
            "context_budgets": [window] if window else [], "default_effort": None,
            "tools": info.get("supports_function_calling") is True,
            "vision": info.get("supports_vision") is True, "efforts": []}


def builder_supported(model: str) -> bool:
    spec = profile(model)
    return spec["tools"] and spec["vision"]


def entry_profile(entry: dict) -> dict:
    params = entry["litellm_params"]
    spec = profile(params["model"])
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
