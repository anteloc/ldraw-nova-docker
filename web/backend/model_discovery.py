"""Best-effort model details, refreshed only when the user clicks Test.

OpenAI's Models API does not publish limits/capabilities/prices: use the sourced
documentation snapshot there. OpenRouter publishes all three; Claude's Models
API publishes input/output limits and selected capabilities, but not pricing.
Never infer unknown features from an OK reply or forward keys to a catalogue.
"""
from datetime import datetime, timezone
import math
from urllib.parse import quote

import httpx

import environment_config
import llm_config
import model_catalog


def positive_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def price(value):
    try:
        number = float(value)
        return round(number * 1_000_000, 8) if math.isfinite(number) and number >= 0 else None
    except (ValueError, TypeError):
        return None


def openrouter_profile(model: str, data: dict) -> dict:
    window = positive_int(data.get("context_length"))
    supported = data.get("supported_parameters")
    architecture = data.get("architecture") or {}
    modalities = architecture.get("input_modalities")
    reasoning = data.get("reasoning") or {}
    efforts = [e for e in ["none", "minimal", *model_catalog.EFFORTS]
               if e in (reasoning.get("supported_efforts") or [])]
    rates = data.get("pricing") or {}
    return {"context_window": window, "context_budgets": [window] if window else [],
            "max_output_tokens": positive_int((data.get("top_provider") or {}).get("max_completion_tokens")),
            "tools": "tools" in supported if isinstance(supported, list) else None,
            "vision": "image" in modalities if isinstance(modalities, list) else None,
            "reasoning": any(p in supported for p in ("reasoning", "reasoning_effort")) if isinstance(supported, list) else None,
            "reasoning_enabled": reasoning.get("default_enabled"),
            "efforts": efforts, "default_effort": reasoning.get("default_effort") if reasoning.get("default_effort") in efforts else None,
            "pricing": {"input": price(rates.get("prompt")), "output": price(rates.get("completion")),
                        "currency": "USD", "note": "Starting API rates per 1M tokens. Longer requests or routing choices may cost more."},
            "source_url": "https://openrouter.ai/" + model.removeprefix("openrouter/"),
            "source_label": "OpenRouter catalogue", "verified_at": datetime.now(timezone.utc).isoformat(),
            "lookup_status": "live"}


async def _fetch_json(client, url, headers=None):
    response = await client.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


async def discover(entry: dict) -> dict:
    model = entry["litellm_params"]["model"]
    spec = model_catalog.profile(model)
    # Arbitrary gateways may serve a different model under a familiar name.
    # Don't attribute public-provider prices or limits to an unknown endpoint.
    base = entry["litellm_params"].get("api_base") or ""
    if isinstance(base, str) and base.startswith("os.environ/"):
        base = environment_config.snapshot().get(base.split("/", 1)[1], "unknown")
    standard_bases = {"openai": {"https://api.openai.com/v1"},
                      "openrouter": {"https://openrouter.ai/api/v1"},
                      "anthropic": {"https://api.anthropic.com", "https://api.anthropic.com/v1"}}
    if base and str(base).rstrip("/") not in standard_bases.get(model.split("/", 1)[0], set()):
        return {**spec, "context_window": None, "context_budgets": [], "max_output_tokens": None,
                "tools": None, "vision": None, "reasoning": None, "efforts": [], "default_effort": None,
                "pricing": None, "source_url": None, "source_label": None, "verified_at": None,
                "lookup_status": "unavailable"}
    spec["lookup_status"] = "published" if spec.get("source_label") else "unavailable"
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            if model.startswith("openrouter/"):
                catalogue = await _fetch_json(client, "https://openrouter.ai/api/v1/models")
                data = next((m for m in catalogue["data"] if m.get("id") == model.removeprefix("openrouter/")), None)
                if data:
                    spec.update(openrouter_profile(model, data))
                else:
                    spec["lookup_status"] = "unavailable"
            elif model.startswith("anthropic/") and entry.get("auth_mode") != "browser":
                params = llm_config.resolve_params(entry)
                key = params.get("api_key") or environment_config.snapshot().get("ANTHROPIC_API_KEY")
                if key:
                    data = await _fetch_json(client, "https://api.anthropic.com/v1/models/" + quote(model.split("/", 1)[1], safe=""),
                                             headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
                    window = positive_int(data.get("max_input_tokens"))
                    if window:
                        spec.update(context_window=window, context_budgets=[window])
                    if positive_int(data.get("max_tokens")):
                        spec["max_output_tokens"] = data["max_tokens"]
                    caps = data.get("capabilities") or {}
                    for ours, theirs in (("vision", "image_input"), ("reasoning", "thinking"), ("tools", "tool_use")):
                        supported = (caps.get(theirs) or {}).get("supported")
                        if isinstance(supported, bool):
                            spec[ours] = supported
                    efforts = caps.get("effort") or {}
                    if efforts:
                        spec["efforts"] = [e for e in model_catalog.EFFORTS if (efforts.get(e) or {}).get("supported") is True]
                        if spec["default_effort"] not in spec["efforts"]:
                            spec["default_effort"] = None
                    spec.update(lookup_status="live", verified_at=datetime.now(timezone.utc).isoformat(),
                                source_label="Claude API + published pricing")
    except Exception:
        # Discovery must not turn a working connection into a failed Test, or
        # expose a provider error that could contain submitted credentials.
        spec["lookup_status"] = "unavailable"
    return spec
