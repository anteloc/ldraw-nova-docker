import asyncio
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

import inference
import agent
import llm_config
import main
import model_catalog
import model_discovery


def test_requested_presets_and_legacy_agents_remain_supported():
    for provider, names in {
        "anthropic": ["Claude Opus 5.5", "Claude Opus 5", "Claude Sonnet 5", "Claude Fable 5", "Claude Fable 5.1"],
        "openai": ["GPT-6 Astra", "GPT-6 Sol", "GPT-5.6 Sol", "GPT-5.6 Terra", "GPT-5.5"],
    }.items():
        assert [m["name"] for m in model_catalog.CATALOG if m["model"].startswith(provider + "/")] == names
    for name in ("openai/gpt-6-luna", "openrouter/openai/gpt-6-sol", "openrouter/anthropic/claude-opus-5.5"):
        assert model_catalog.builder_supported(name)


def test_test_refreshes_context_prices_and_persists_without_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(main.settings, "CONFIG_DIR", tmp_path)
    async def fetch(client, url, headers=None):
        assert url == "https://openrouter.ai/api/v1/models" and headers is None
        return {"data": [{"id": "x-ai/grok-4.20", "context_length": 1_500_000,
                          "top_provider": {"max_completion_tokens": 64_000},
                          "supported_parameters": ["tools", "reasoning"], "architecture": {"input_modalities": ["text", "image"]},
                          "reasoning": {"supported_efforts": ["low", "high"], "default_effort": "high"},
                          "pricing": {"prompt": "0.0000004", "completion": "0.000002"}}]}
    async def complete(**params):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))])
    monkeypatch.setattr(model_discovery, "_fetch_json", fetch)
    monkeypatch.setattr(main.litellm, "acompletion", complete)
    client = TestClient(main.app)
    entry = client.post("/api/llm-models", json={"litellm_params": {"model": "openrouter/x-ai/grok-4.20", "api_key": "secret-metadata-key"}}).json()
    result = client.post(f"/api/llm-models/{entry['id']}/test").json()
    assert result["ok"] and result["connection_status"] == "connected"
    profile = result["profile"]
    assert profile["context_budgets"] == [1_500_000]
    assert profile["pricing"]["input"] == .4 and profile["pricing"]["output"] == 2
    assert profile["efforts"] == ["low", "high"] and profile["default_effort"] == "high"
    assert profile["lookup_status"] == "live" and profile["verified_at"]
    persisted = client.get(f"/api/llm-models/{entry['id']}/edit")
    assert persisted.json()["profile"] == profile
    assert "secret-metadata-key" not in persisted.text
    assert "fingerprint" not in persisted.text and "_connection_test" not in persisted.text
    stored = llm_config.get(entry["id"])
    assert model_catalog.validate_options(stored, {})["context_tokens"] == 1_500_000
    changed = client.put(f"/api/llm-models/{entry['id']}", json={"litellm_params": {"model": "openai/gpt-6-sol"}}).json()
    assert changed["connection_status"] == "not_tested" and changed["profile"]["context_window"] == 1_050_000


def test_missing_metadata_is_unknown_and_false_is_not_unknown():
    empty = model_discovery.openrouter_profile("openrouter/test/model", {})
    assert all(empty[k] is None for k in ("context_window", "max_output_tokens", "tools", "vision", "reasoning"))
    assert empty["pricing"]["input"] is None
    absent = model_discovery.openrouter_profile("openrouter/test/model", {
        "supported_parameters": [], "architecture": {"input_modalities": ["text"]},
        "pricing": {"prompt": "-1", "completion": "nan"}})
    assert absent["tools"] is False and absent["vision"] is False
    assert absent["pricing"]["input"] is None and absent["pricing"]["output"] is None


def test_unavailable_lookup_uses_sourced_fallback_without_changing_test_result(monkeypatch, tmp_path):
    monkeypatch.setattr(main.settings, "CONFIG_DIR", tmp_path)
    async def complete(**params):
        raise ValueError("private-token-must-not-escape")
    monkeypatch.setattr(main.litellm, "acompletion", complete)
    entry = llm_config.create({"litellm_params": {"model": "openrouter/x-ai/grok-4.20", "api_key": "test"}})
    result = TestClient(main.app).post(f"/api/llm-models/{entry['id']}/test")
    assert not result.json()["ok"]
    assert result.json()["profile"]["context_window"] == 2_000_000
    assert result.json()["profile"]["lookup_status"] == "unavailable"
    assert "private-token" not in result.text
    status = llm_config.record_connection_test(entry["id"], "outdated-fingerprint", True, {"context_window": 123})
    assert status == "not_tested"
    assert llm_config.public(llm_config.get(entry["id"]))["profile"]["context_window"] == 2_000_000


def test_claude_model_api_limits_and_capabilities(monkeypatch):
    async def fetch(client, url, headers=None):
        assert url == "https://api.anthropic.com/v1/models/claude-fable-5-1"
        assert headers["x-api-key"] == "test-only-secret"
        return {"max_input_tokens": 800_000, "max_tokens": 32_000, "capabilities": {
            "image_input": {"supported": True}, "thinking": {"supported": True},
            "effort": {"supported": True, "high": {"supported": True}, "max": {"supported": False}}}}
    monkeypatch.setattr(model_discovery, "_fetch_json", fetch)
    spec = asyncio.run(model_discovery.discover({"litellm_params": {"model": "anthropic/claude-fable-5-1", "api_key": "test-only-secret"}}))
    assert spec["context_budgets"] == [800_000] and spec["max_output_tokens"] == 32_000
    assert spec["efforts"] == ["high"] and spec["pricing"]["input"] == 10
    assert "test-only-secret" not in json.dumps(spec)


def test_custom_gateway_has_unknown_limits_and_on_off_reasoning_is_enabled():
    entry = {"litellm_params": {"model": "openai/gpt-6-sol", "api_base": "https://custom.invalid/v1"}}
    spec = asyncio.run(model_discovery.discover(entry))
    assert spec["context_window"] is None and spec["pricing"] is None and spec["tools"] is None
    entry = {"litellm_params": {"model": "openrouter/x-ai/grok-4.20", "api_key": "test"}}
    assert asyncio.run(inference.params_for(entry, {}))["extra_body"]["reasoning"] == {"enabled": True}


def test_provider_rejecting_builder_capability_prevents_a_new_turn(monkeypatch, tmp_path):
    import pytest
    monkeypatch.setattr(main.settings, "CONFIG_DIR", tmp_path)
    entry = llm_config.create({"litellm_params": {"model": "openrouter/x-ai/grok-4.20"}})
    llm_config.record_connection_test(entry["id"], llm_config.connection_fingerprint(entry), True, {"tools": False, "vision": True})
    assert llm_config.public(llm_config.get(entry["id"]))["resolved_capabilities"]["tools"] is False
    with pytest.raises(ValueError, match="tool calling and image input"):
        asyncio.run(agent.start_turn(None, "unused-chat", "Build a car", entry["id"]))


def test_explicit_standard_api_base_still_discovers_metadata(monkeypatch):
    calls = []
    async def fetch(client, url, headers=None):
        calls.append(url)
        return {"data": [{"id": "x-ai/grok-4.20", "context_length": 2_000_000}]}
    monkeypatch.setattr(model_discovery, "_fetch_json", fetch)
    monkeypatch.setenv("TEST_METADATA_BASE", "https://openrouter.ai/api/v1/")
    for base in ("https://openrouter.ai/api/v1", "os.environ/TEST_METADATA_BASE"):
        result = asyncio.run(model_discovery.discover({"litellm_params": {"model": "openrouter/x-ai/grok-4.20", "api_base": base}}))
        assert result["lookup_status"] == "live" and result["context_window"] == 2_000_000
    assert len(calls) == 2
