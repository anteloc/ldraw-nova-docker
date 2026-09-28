import asyncio

import pytest
from fastapi.testclient import TestClient

import inference
import llm_config
import model_catalog
from main import app


def test_visible_effort_matches_the_effective_request():
    for model, default in [
        ("openai/gpt-6-sol", "medium"),
        ("anthropic/claude-opus-5-5", "medium"),
        ("openrouter/anthropic/claude-opus-5.5", "high"),
        ("anthropic/claude-sonnet-5", "high"),
    ]:
        entry = {"litellm_params": {"model": model, "api_key": "test"}}
        assert llm_config.public(entry)["profile"]["default_effort"] == default
        options = model_catalog.validate_options(entry, {})
        assert options["effort"] == default
        params = asyncio.run(inference.params_for(entry, options))
        if model.startswith("openrouter/"):
            assert params["extra_body"]["reasoning"]["effort"] == default
        elif model.startswith("anthropic/"):
            assert params["output_config"]["effort"] == default
        else:
            assert params["reasoning_effort"] == default
    entry = {"litellm_params": {"model": "openrouter/openai/gpt-6-sol", "extra_body": {"reasoning": {"effort": "max"}}}}
    assert llm_config.public(entry)["profile"]["default_effort"] == "max"
    assert model_catalog.validate_options(entry, {})["effort"] == "max"


def test_context_choices_are_model_windows_and_chat_mode_is_rejected(monkeypatch):
    for model, window in [("openai/gpt-6-sol", 1_050_000), ("anthropic/claude-haiku-4-5-20251001", 200_000)]:
        spec = model_catalog.profile(model)
        entry = {"litellm_params": {"model": model}}
        assert spec["context_budgets"] == [window]
        assert model_catalog.validate_options(entry, {})["context_tokens"] == window
        with pytest.raises(ValueError, match="context budget"):
            model_catalog.validate_options(entry, {"context_tokens": 32_000})
        with pytest.raises(ValueError, match="mode"):
            model_catalog.validate_options(entry, {"mode": "chat"})
    monkeypatch.setattr(model_catalog.litellm, "get_model_info", lambda _: {
        "supports_function_calling": True, "supports_vision": True, "max_input_tokens": 16_000})
    assert model_catalog.profile("custom/small")["context_budgets"] == [16_000]


def test_unsupported_models_cannot_override_capabilities_or_partially_import(monkeypatch):
    monkeypatch.setattr(model_catalog.litellm, "get_model_info", lambda _: {
        "supports_function_calling": True, "supports_vision": False, "max_input_tokens": 128_000})
    client = TestClient(app)
    unsupported = {"model_name": "unsupported", "litellm_params": {"model": "custom/text-only"},
                   "capabilities": {"tools": True, "vision": True}}
    assert client.post("/api/llm-models", json=unsupported).status_code == 400
    before = llm_config.list_entries()
    with pytest.raises(ValueError, match="image input"):
        llm_config.import_model_list([{"litellm_params": {"model": "openai/gpt-6-sol"}}, unsupported])
    assert llm_config.list_entries() == before
    entry = llm_config.create({"litellm_params": {"model": "openai/gpt-6-sol"}})
    assert client.put(f"/api/llm-models/{entry['id']}", json=unsupported).status_code == 400
    assert llm_config.get(entry["id"])["litellm_params"]["model"] == "openai/gpt-6-sol"


def test_edit_reveals_key_without_unmasking_list_or_export():
    client = TestClient(app)
    entry = client.post("/api/llm-models", json={"litellm_params": {
        "model": "openrouter/openai/gpt-6-sol", "api_key": "visible-test-key-9876"}}).json()
    edit = client.get(f"/api/llm-models/{entry['id']}/edit")
    assert edit.json()["litellm_params"]["api_key"] == "visible-test-key-9876"
    assert edit.headers["cache-control"] == "no-store"
    assert "visible-test-key" not in client.get("/api/llm-models").text
    assert "visible-test-key" not in client.get("/api/llm-models/export").text
    assert client.get(f"/api/llm-models/{entry['id']}/edit", headers={"Origin": "https://other.example"}).status_code == 403
    client.put(f"/api/llm-models/{entry['id']}", json={"litellm_params": {
        "model": "openrouter/openai/gpt-6-sol", "api_key": "os.environ/OPENROUTER_API_KEY"}})
    assert client.get(f"/api/llm-models/{entry['id']}/edit").json()["litellm_params"]["api_key"] == "os.environ/OPENROUTER_API_KEY"
