import asyncio
import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agent
import llm_config
import settings
from attachments import save_documents, validate_documents, validate_images
from main import app
from store import ChatStore
from tools import ToolContext, t_read_file


def upload(name="brief.md", content=b"# Build a courtyard\nUse tan bricks."):
    return {"name": name, "data": "data:application/octet-stream;base64," + base64.b64encode(content).decode()}


@pytest.mark.parametrize("document", [
    upload("../brief.md"), upload("nested/brief.md"), upload("nested\\brief.md"), upload(".hidden.md"),
    upload("bad\nname.md"), upload("script.exe"), upload("image.png"), upload(content=b"\x89PNG\r\n\x1a\n"),
    {"name": "brief.md", "data": "https://example.com/brief.md"},
    {"name": "brief.md", "data": "data:text/plain;base64,not valid"},
    upload(content=b"x" * (5 * 1024 * 1024 + 1)),
])
def test_reject_invalid_document_uploads(document):
    with pytest.raises(ValueError):
        validate_documents([document])


def test_combined_limits_and_document_count():
    with pytest.raises(ValueError, match="four"):
        validate_documents([upload()] * 5)
    images = validate_images(["data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024 - 8)).decode()])
    with pytest.raises(ValueError, match="total"):
        validate_documents([upload(content=b"x" * (4 * 1024 * 1024))] * 2, images)


def test_uploads_cannot_follow_a_symlink_outside_the_chat(tmp_path):
    store = ChatStore(tmp_path / "chats", tmp_path / "output")
    chat = store.create_chat()
    outside = tmp_path / "private"
    outside.mkdir()
    (store.work_dir(chat["id"]) / "uploads").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="workspace"):
        save_documents(store, chat["id"], validate_documents([upload()]))
    assert list(outside.iterdir()) == []


def test_documents_persist_and_are_available_to_both_agent_adapters(monkeypatch):
    async def no_inference(*args):
        pass
    monkeypatch.setattr(agent, "_run_turn", no_inference)
    store = ChatStore(settings.CHATS_DIR, settings.OUTPUT_DIR)
    chat = store.create_chat()
    entry = llm_config.create({"litellm_params": {"model": "openai/gpt-6-sol", "api_key": "fake"}})
    image = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()
    with TestClient(app) as client:
        for _ in range(2):
            r = client.post(f"/api/chats/{chat['id']}/messages", json={"text": "Build from these references",
                "llm_model_id": entry["id"], "images": [image], "documents": [upload(), upload("reference.pdf", b"%PDF-1.7\nexample")]})
            assert r.status_code == 202, r.text
        messages = store.messages(chat["id"])
        doc = messages[0]["_documents"][0]
        path = store.resolve(chat["id"], doc["path"])
        assert path.is_relative_to(store.work_dir(chat["id"]) / "uploads")
        assert path != store.resolve(chat["id"], messages[1]["_documents"][0]["path"])
        assert path.read_text().startswith("# Build a courtyard")
        ctx = ToolContext(chat["id"], store, lambda *_: None)
        assert "Use tan bricks" in asyncio.run(t_read_file(ctx, str(path))).content
        for model in ("openai/gpt-6-sol", "anthropic/claude-opus-5"):
            history = agent.llm_history(messages, True, lambda ref: store.resolve(chat["id"], ref), model)
            assert str(path) in history[0]["content"][-1]["text"]
            assert history[0]["content"][1]["image_url"]["url"] == image
            assert "_documents" not in history[0]
        detail = client.get(f"/api/chats/{chat['id']}").json()
        public_doc = detail["messages"][0]["_documents"][0]
        response = client.get(public_doc["url"])
        assert response.content == path.read_bytes()
        assert "attachment" in response.headers["content-disposition"]
        assert "sandbox" in response.headers["content-security-policy"]
        other_chat = store.create_chat()
        assert client.get(public_doc["url"].replace(chat["id"], other_chat["id"])).status_code == 404
        assert detail["messages"][0]["content"][0]["text"] == "Build from these references"
