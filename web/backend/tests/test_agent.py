import asyncio
import json
from pathlib import Path

import pytest
from litellm.types.utils import ChatCompletionDeltaToolCall, Delta, Function, ModelResponseStream, StreamingChoices

import agent
import llm_config
import settings
from store import ChatStore

CAR = "0 FILE car.ldr\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n1 15 0 -24 0 1 0 0 0 1 0 0 0 1 3003.dat\n"


def chunk(**delta) -> ModelResponseStream:
    return ModelResponseStream(id="t", model="fake", choices=[StreamingChoices(index=0, delta=Delta(**delta))])


def tool_call_chunks(call_id: str, name: str, args: dict) -> list[ModelResponseStream]:
    return [
        chunk(tool_calls=[ChatCompletionDeltaToolCall(index=0, id=call_id, type="function",
                                                      function=Function(name=name, arguments=""))]),
        chunk(tool_calls=[ChatCompletionDeltaToolCall(index=0, function=Function(arguments=json.dumps(args)))]),
    ]


def scripted(responses: list[list[ModelResponseStream]]):
    """A stand-in for litellm.acompletion that streams the given responses in order."""
    calls: list[dict] = []

    async def acompletion(**kwargs):
        calls.append(kwargs)
        chunks = responses[len(calls) - 1]

        async def stream():
            for c in chunks:
                yield c
        return stream()

    return acompletion, calls


@pytest.fixture
def store() -> ChatStore:
    return ChatStore(settings.CHATS_DIR, settings.OUTPUT_DIR)


@pytest.fixture
def entry():
    return llm_config.create({"model_name": "fake", "litellm_params": {"model": "openai/gpt-6-luna", "api_key": "sk-x"},
                              "capabilities": {"tools": True, "vision": True}})


def test_llm_history_repairs_interrupted_tool_calls():
    calls = [{"id": i, "type": "function", "function": {"name": "find_parts", "arguments": "{}"}} for i in ("a", "b")]
    stored = [
        {"id": 1, "role": "user", "content": "hi", "created_at": 0},
        {"id": 2, "role": "assistant", "content": None, "tool_calls": calls},
        {"id": 3, "role": "tool", "tool_call_id": "a", "name": "find_parts", "content": "ok", "_models": []},
        {"id": 4, "role": "assistant", "content": "Stopped.", "_ui_only": True},
        {"id": 5, "role": "user", "content": "again"},
    ]
    out = agent.llm_history(stored, vision=False, resolve=Path)
    assert [m["role"] for m in out] == ["user", "assistant", "tool", "tool", "user"]
    assert out[3]["tool_call_id"] == "b" and "interrupted" in out[3]["content"]
    assert all(not k.startswith("_") and k not in ("id", "created_at") for m in out for k in m)


def test_llm_history_sends_only_newest_images(tmp_path: Path):
    stored = []
    for i in range(3):
        (tmp_path / f"r{i}.png").write_bytes(b"\x89PNG fake")
        stored.append({"id": i, "role": "user", "content": "renders", "_images_for_llm": [f"r{i}.png"]})
    resolve = lambda ref: tmp_path / ref  # noqa: E731
    with_vision = agent.llm_history(stored, vision=True, resolve=resolve)
    assert len(with_vision) == agent.KEEP_IMAGE_MESSAGES
    assert with_vision[-1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert agent.llm_history(stored, vision=False, resolve=resolve) == []


def test_turn_runs_tool_saves_renders_and_answers(monkeypatch, entry, store: ChatStore):
    fake, calls = scripted([
        [chunk(role="assistant", content="Building it. "),
         *tool_call_chunks("c1", "run_toolkit", {"arguments": ["build", "examples/bridge.plan.json", "--output", "output/bridge.mpd"]})],
        [*tool_call_chunks("c2", "publish_model", {"path": "output/bridge.mpd", "name": "Agent bridge"})],
        [*tool_call_chunks("c3", "view_image", {"path": str(settings.GENERATED_DIR / "agent-bridge-v1.png")})],
        [chunk(content="Done.")],
    ])
    monkeypatch.setattr(agent.litellm, "acompletion", fake)
    import os
    os.chmod(settings.DATA_DIR.parent, 0o755)
    chat = store.create_chat()
    (store.work_dir(chat["id"]) / "NOTES.md").write_text("plan: example bridge")

    async def run():
        await agent.start_turn(store, chat["id"], "build an example bridge", entry["id"], {"permissions": "full"})
        await agent._runs[chat["id"]].task

    asyncio.run(run())
    messages = store.messages(chat["id"])
    assert messages[-1]["content"] == "Done.", messages
    [ref] = store.models(chat["id"])
    model = settings.GENERATED_DIR / "agent-bridge-v1.mpd"
    assert model.read_bytes() == (store.work_dir(chat["id"]) / "bridge.mpd").read_bytes()
    assert model.with_suffix(".png").stat().st_size > 1000
    assert any(ref["id"] in m.get("_models", []) for m in messages)
    assert any(m.get("_images_for_llm") for m in messages)
    assert "NOTES.md" in calls[0]["messages"][0]["content"]
    assert isinstance(calls[-1]["messages"][-1]["content"], list)


def test_provider_error_ends_turn_but_not_chat(monkeypatch, entry, store: ChatStore):
    async def broken(**_kwargs):
        raise RuntimeError("401 invalid api key")
    monkeypatch.setattr(agent.litellm, "acompletion", broken)
    chat = store.create_chat()

    async def run():
        await agent.start_turn(store, chat["id"], "hello", entry["id"])
        await agent._runs[chat["id"]].task

    asyncio.run(run())
    last = store.messages(chat["id"])[-1]
    assert last["_error"] and "Provider request failed" in last["content"]
    assert not agent.is_running(chat["id"])
