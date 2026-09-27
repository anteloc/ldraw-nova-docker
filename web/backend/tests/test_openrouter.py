import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import litellm
import pytest
from fastapi.testclient import TestClient

import inference
import llm_config
import model_catalog
import agent
import settings
from main import app
from store import ChatStore


def test_openrouter_presets_and_capabilities():
    presets = model_catalog.OPENROUTER_CATALOG
    assert len(presets) == 8
    assert {p["model"] for p in presets} >= {
        "openrouter/openai/gpt-6-astra", "openrouter/anthropic/claude-opus-5.5",
        "openrouter/anthropic/claude-haiku-4.5"}
    for preset in presets:
        entry = {"litellm_params": {"model": preset["model"]}}
        assert llm_config.capabilities(entry) == {"tools": True, "vision": True}
        assert model_catalog.profile(preset["model"])["context_budgets"]
    astra = {"litellm_params": {"model": "openrouter/openai/gpt-6-astra"}}
    assert model_catalog.validate_options(astra, {"effort": "max"})["effort"] == "max"
    with pytest.raises(ValueError, match="effort"):
        model_catalog.validate_options(astra, {"effort": "none"})
    assert model_catalog.profile("openrouter/anthropic/claude-haiku-4.5")["efforts"] == []
    client = TestClient(app)
    suggestions = client.get("/api/llm-providers/openrouter/models").json()["models"]
    assert all(p["model"] in suggestions for p in presets)


def test_openrouter_key_reference_and_private_key_roundtrip(monkeypatch):
    client = TestClient(app)
    reference = "os.environ/OPENROUTER_LDRAW_ASTRA_API_KEY"
    monkeypatch.setenv("OPENROUTER_LDRAW_ASTRA_API_KEY", "private-test-key")
    response = client.post("/api/llm-models", json={"litellm_params": {
        "model": "openrouter/openai/gpt-6-luna", "api_key": reference}})
    assert response.status_code == 200
    public = response.json()
    assert public["auth_mode"] == "api_key"
    assert public["litellm_params"]["api_key"] == reference
    entry = llm_config.get(public["id"])
    assert llm_config.resolve_params(entry)["api_key"] == "private-test-key"
    monkeypatch.setenv("OPENROUTER_LDRAW_ASTRA_API_KEY", "")
    with pytest.raises(ValueError, match="not set or is empty"):
        llm_config.resolve_params(entry)
    monkeypatch.delenv("OPENROUTER_LDRAW_ASTRA_API_KEY")
    assert not client.post(f"/api/llm-models/{entry['id']}/test").json()["ok"]
    public["litellm_params"]["api_key"] = "sk-or-private-test-key"
    public = client.put(f"/api/llm-models/{entry['id']}", json=public).json()
    assert public["litellm_params"]["api_key"].startswith("••••")
    client.put(f"/api/llm-models/{entry['id']}", json=public)
    assert llm_config.resolve_params(llm_config.get(entry["id"]))["api_key"] == "sk-or-private-test-key"
    assert "sk-or-private-test-key" not in client.get("/api/llm-models/export").text
    assert client.post("/api/llm-models", json={"litellm_params": {"model": "openrouter/"}}).status_code == 400
    assert client.post("/api/llm-models", json={"auth_mode": "browser", "litellm_params": {
        "model": "openrouter/openai/gpt-6-luna"}}).status_code == 400


@pytest.fixture
def stream_deltas():
    return []


@pytest.fixture
def endpoint(stream_deltas):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, body, self.headers.get("Authorization")))
            base = {"id": "test", "created": 1, "model": body["model"]}
            if body.get("stream"):
                deltas = stream_deltas.pop(0) if stream_deltas else [{"role": "assistant", "content": "OK"}]
                chunks = [
                    {**base, "object": "chat.completion.chunk", "choices": [{"index": 0,
                     "delta": delta, "finish_reason": None}]} for delta in deltas
                ] + [
                    {**base, "object": "chat.completion.chunk", "choices": [{"index": 0,
                     "delta": {}, "finish_reason": "tool_calls" if any(d.get("tool_calls") for d in deltas) else "stop"}]},
                ]
                payload = ("".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n").encode()
                content_type = "text/event-stream"
            else:
                payload = json.dumps({**base, "object": "chat.completion", "choices": [{"index": 0,
                    "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}]}).encode()
                content_type = "application/json"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("model", ["openai/gpt-6-astra", "anthropic/claude-opus-5.5"])
@pytest.mark.parametrize("stream", [False, True])
def test_openrouter_http_preserves_model_key_effort_tools_and_images(endpoint, model, stream):
    base, requests = endpoint
    entry = {"auth_mode": "api_key", "litellm_params": {
        "model": "openrouter/" + model, "api_key": "private-test-key", "api_base": base,
        "extra_body": {"provider": {"require_parameters": True}}}}
    image = "data:image/png;base64,iVBORw0KGgo="

    async def run():
        params = await inference.params_for(entry, {"effort": "max"})
        result = await litellm.acompletion(**params, stream=stream, num_retries=0, timeout=10,
            messages=[{"role": "user", "content": [{"type": "text", "text": "Reply OK"},
                      {"type": "image_url", "image_url": {"url": image}}]}],
            tools=[{"type": "function", "function": {"name": "list_files", "description": "List files",
                    "parameters": {"type": "object", "properties": {}}}}])
        if stream:
            chunks = [c async for c in result]
            result = litellm.stream_chunk_builder(chunks)
        assert result.choices[0].message.content == "OK"

    asyncio.run(run())
    assert len(requests) == 1
    path, body, authorization = requests[0]
    assert path == "/api/v1/chat/completions"
    assert authorization == "Bearer private-test-key"
    assert body["model"] == model
    assert body["reasoning"] == {"effort": "max"}  # must not silently become xhigh
    assert "reasoning_effort" not in body and "thinking" not in body
    assert body["provider"] == {"require_parameters": True}
    assert body["messages"][0]["content"][1]["image_url"]["url"] == image
    assert body["tools"][0]["function"]["name"] == "list_files"


def test_agent_roundtrips_streamed_reasoning_through_tools_storage_and_http(endpoint, stream_deltas):
    base, requests = endpoint
    model = "openrouter/openai/gpt-6-sol"
    details = [
        {"type": "reasoning.summary", "summary": "Synthetic test summary.", "id": "rs_test", "index": 0,
         "format": "openai-responses-v1"},
        {"type": "reasoning.encrypted", "data": "opaque-test-block-a", "id": "rs_test", "index": 0,
         "format": "openai-responses-v1"},
        {"type": "reasoning.encrypted", "data": "opaque-test-block-b", "id": "rs_next", "index": 1,
         "format": "openai-responses-v1"},
    ]
    stream_deltas.append([
        {"role": "assistant", "reasoning": "Synthetic plain reasoning.", "reasoning_details": details[:1]},
        {"reasoning_details": details[1:]},
        {"tool_calls": [{"index": 0, "id": "call_test", "type": "function", "function": {
            "name": "report_progress", "arguments": json.dumps({"summary": "Designing the model."})}}]},
    ])
    entry = {"auth_mode": "api_key", "litellm_params": {
        "model": model, "api_key": "private-test-key", "api_base": base}}
    store = ChatStore(settings.CHATS_DIR, settings.OUTPUT_DIR)
    chat_id = store.create_chat()["id"]
    store.add_message(chat_id, {"role": "user", "content": "Build me a car"})
    run = agent.Run(chat_id, options={"mode": "agent", "permissions": "full"})
    events = []
    run.emit = lambda event, data: events.append((event, data))

    asyncio.run(agent._run_turn(store, run, entry))

    assert len(requests) == 2, store.messages(chat_id)[-1]
    continued = next(m for m in requests[1][1]["messages"] if m["role"] == "assistant")
    assert continued["reasoning_details"] == details
    assert continued["tool_calls"][0]["id"] == "call_test"
    assert any(m["role"] == "tool" and m["tool_call_id"] == "call_test" for m in requests[1][1]["messages"])
    assert not any(k.startswith("_") for k in continued)
    stored = ChatStore(settings.CHATS_DIR, settings.OUTPUT_DIR).messages(chat_id)
    assert stored[1]["_reasoning_details"] == details
    assert stored[-1]["content"] == "OK"
    assert "opaque-test" not in json.dumps(events)
    assert "opaque-test" not in TestClient(app).get(f"/api/chats/{chat_id}").text
    assert agent.llm_history(stored, False, lambda _: None, model)[1]["reasoning_details"] == details
    for other in ("openrouter/openai/gpt-6-astra", "openai/gpt-6-sol", "anthropic/claude-opus-5.5"):
        assert "reasoning_details" not in agent.llm_history(stored, False, lambda _: None, other)[1]


def test_old_openrouter_history_preserves_plain_reasoning_only_for_same_model():
    model = "openrouter/openai/gpt-6-sol"
    stored = [{"role": "assistant", "content": "Working.", "_llm_model": model,
               "_reasoning": "Synthetic legacy reasoning."}]
    assert agent.llm_history(stored, False, lambda _: None, model)[0]["reasoning_content"] == stored[0]["_reasoning"]
    assert "reasoning_content" not in agent.llm_history(stored, False, lambda _: None, "openai/gpt-6-sol")[0]
