"""Exercise the installed LiteLLM bridge, with only the HTTP server faked."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import litellm
import pytest
from litellm.llms.chatgpt.authenticator import Authenticator

import browser_auth
import inference


@pytest.fixture
def chatgpt_endpoint(monkeypatch):
    requests = []
    output = {"id": "msg_test", "type": "message", "role": "assistant",
              "status": "completed", "content": [{"type": "output_text", "text": "OK", "annotations": []}]}
    response = {"id": "resp_test", "object": "response", "created_at": 1,
                "model": "gpt-6-astra", "status": "completed", "output": [output],
                "usage": {"input_tokens": 10, "output_tokens": 1, "total_tokens": 11}}
    events = [
        {"type": "response.created", "response": {**response, "status": "in_progress", "output": []}},
        {"type": "response.output_item.added", "output_index": 0,
         "item": {**output, "status": "in_progress", "content": []}},
        {"type": "response.content_part.added", "output_index": 0, "content_index": 0,
         "item_id": "msg_test", "part": {"type": "output_text", "text": "", "annotations": []}},
        {"type": "response.output_text.delta", "output_index": 0, "content_index": 0,
         "item_id": "msg_test", "delta": "OK"},
        {"type": "response.output_text.done", "output_index": 0, "content_index": 0,
         "item_id": "msg_test", "text": "OK"},
        {"type": "response.output_item.done", "output_index": 0, "item": output},
        {"type": "response.completed", "response": response},
    ]
    payload = "".join(f"event: {event['type']}\ndata: {json.dumps({**event, 'sequence_number': i})}\n\n"
                      for i, event in enumerate(events)).encode()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, body, {k.lower(): v for k, v in self.headers.items()}))
            if self.path != "/responses":
                self.send_error(404, "ChatGPT only supports Responses")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("CHATGPT_API_BASE", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setattr(Authenticator, "get_access_token", lambda self: "test-session")
    monkeypatch.setattr(Authenticator, "get_account_id", lambda self: "test-account")

    async def ready():
        pass

    monkeypatch.setattr(browser_auth, "openai_ready", ready)
    try:
        yield requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("stream", [False, True])
def test_chatgpt_new_model_uses_responses_even_without_catalog_entry(chatgpt_endpoint, stream):
    async def run():
        entry = {"auth_mode": "browser", "litellm_params": {"model": "openai/gpt-6-astra"}}
        params = await inference.params_for(entry, {"effort": "low"})
        messages = [{"role": "system", "content": "You are the LDraw assistant."},
                    {"role": "user", "content": "Reply OK."}]
        result = await litellm.acompletion(**params, messages=messages, stream=stream,
                                          num_retries=0, timeout=10, max_tokens=4096,
                                          tools=[{"type": "function", "function": {
                                              "name": "list_files", "description": "List files",
                                              "parameters": {"type": "object", "properties": {}}}}])
        if stream:
            chunks = [chunk async for chunk in result]
            assert "".join(c.choices[0].delta.content or "" for c in chunks if c.choices) == "OK"
            result = litellm.stream_chunk_builder(chunks, messages=messages)
        assert result.choices[0].message.content == "OK"

    asyncio.run(run())
    assert len(chatgpt_endpoint) == 1
    path, body, headers = chatgpt_endpoint[0]
    assert path == "/responses"
    assert body["model"] == "gpt-6-astra"
    assert body.get("stream") is True and body.get("store") is False, list(body)
    assert body["reasoning"]["effort"] == "low"
    assert body["instructions"]
    assert body["tools"][0]["name"] == "list_files"
    assert "messages" not in body and "max_output_tokens" not in body
    assert "reasoning.encrypted_content" in body["include"]
    assert headers["authorization"] == "Bearer test-session"
