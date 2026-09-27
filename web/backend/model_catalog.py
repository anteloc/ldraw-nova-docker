"""Verified presets; custom LiteLLM IDs remain available as providers add models.

Capabilities checked against provider documentation on 2026-09-27. Context
choices are application history budgets, not a way to enlarge a model window.
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


def profile(model: str) -> dict:
    canonical = model.replace("chatgpt/", "openai/", 1).replace("responses/", "")
    known = next((m for m in CATALOG if m["model"] == canonical), None)
    if known:
        return {**known, "tools": True, "vision": True,
                "context_budgets": [n for n in (32_000, 128_000, 200_000, 1_000_000) if n <= known["context_window"]]}
    try:
        info = litellm.get_model_info(model)
    except Exception:
        info = {}
    window = info.get("max_input_tokens")
    return {"model": model, "name": model, "context_window": window,
            "context_budgets": [n for n in (32_000, 128_000, 200_000, 1_000_000) if window and n <= window],
            "efforts": []}


def validate_options(entry: dict, options: dict | None) -> dict:
    value = {"mode": "agent", "permissions": "ask", "effort": None, "context_tokens": None, **(options or {})}
    if value["mode"] not in ("chat", "plan", "agent"):
        raise ValueError("Unknown mode")
    if value["permissions"] not in ("ask", "full", "read_only"):
        raise ValueError("Unknown permission setting")
    spec = profile(entry["litellm_params"]["model"])
    if value["effort"] and value["effort"] not in spec["efforts"]:
        raise ValueError("This effort is not supported by the selected model")
    if value["context_tokens"] is not None and value["context_tokens"] not in spec["context_budgets"]:
        raise ValueError("This context budget is not supported by the selected model")
    return value
