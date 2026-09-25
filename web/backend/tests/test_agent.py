import asyncio
import json
from pathlib import Path

import pytest
from litellm.types.utils import ChatCompletionDeltaToolCall, Delta, Function, ModelResponseStream, StreamingChoices

import agent
import llm_config
from store import Store

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
def entry():
    return llm_config.create({"model_name": "fake", "litellm_params": {"model": "openai/fake", "api_key": "sk-x"},
                              "capabilities": {"tools": True, "vision": True}})


def test_llm_history_repairs_interrupted_tool_calls():
    calls = [{"id": i, "type": "function", "function": {"name": "find_parts", "arguments": "{}"}} for i in ("a", "b")]
    stored = [
        {"id": 1, "role": "user", "content": "hi", "created_at": 0},
        {"id": 2, "role": "assistant", "content": None, "tool_calls": calls},
        {"id": 3, "role": "tool", "tool_call_id": "a", "name": "find_parts", "content": "ok", "_artifacts": []},
        {"id": 4, "role": "assistant", "content": "Stopped.", "_ui_only": True},
        {"id": 5, "role": "user", "content": "again"},
    ]
    out = agent.llm_history(stored, vision=False)
    assert [m["role"] for m in out] == ["user", "assistant", "tool", "tool", "user"]
    assert out[3]["tool_call_id"] == "b" and "interrupted" in out[3]["content"]
    assert all(not k.startswith("_") and k not in ("id", "created_at") for m in out for k in m)


def test_llm_history_sends_only_newest_images(data_dir: Path):
    (data_dir / "output").mkdir(parents=True, exist_ok=True)
    stored = []
    for i in range(3):
        png = data_dir / "output" / f"r{i}.png"
        png.write_bytes(b"\x89PNG fake")
        stored.append({"id": i, "role": "user", "content": "renders", "_images_for_llm": [f"output/r{i}.png"]})
    with_vision = agent.llm_history(stored, vision=True)
    assert len(with_vision) == agent.KEEP_IMAGE_MESSAGES
    assert with_vision[-1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert agent.llm_history(stored, vision=False) == []


def test_turn_runs_tool_saves_renders_and_answers(monkeypatch, entry, tmp_path: Path, data_dir: Path):
    fake, calls = scripted([
        [chunk(role="assistant", content="Saving it. "), *tool_call_chunks("c1", "save_model", {"name": "Tiny Car", "content": CAR})],
        [chunk(content="Done.")],
    ])
    monkeypatch.setattr(agent.litellm, "acompletion", fake)
    store = Store(tmp_path / "chats.sqlite")
    chat = store.create_chat()

    async def run():
        await agent.start_turn(store, chat["id"], "build a tiny car", entry["id"])
        await agent._runs[chat["id"]].task

    asyncio.run(run())

    messages = store.messages(chat["id"])
    assert [m["role"] for m in messages] == ["user", "assistant", "tool", "user", "assistant"]
    assert messages[-1]["content"] == "Done."
    assert messages[3]["_hidden"] and messages[3]["_images_for_llm"]           # vision feedback
    [artifact] = store.list_artifacts(chat["id"])
    assert artifact["name"] == "Tiny Car" and artifact["warnings"] == []
    assert artifact["model_path"] == f"generated/{chat['id']}/tiny-car-v1.mpd"
    assert (data_dir / artifact["image_path"]).stat().st_size > 1000             # LeoCAD really rendered it
    assert messages[2]["_artifacts"] == [artifact["id"]]
    # The second LLM call saw the tool result and the render as an image.
    second = calls[1]["messages"]
    assert second[0]["role"] == "system" and any(m["role"] == "tool" for m in second)
    assert isinstance(second[-1]["content"], list)
    assert store.get_chat(chat["id"])["title"] == "build a tiny car"


def test_provider_error_ends_turn_but_not_chat(monkeypatch, entry, tmp_path: Path):
    async def broken(**_kwargs):
        raise RuntimeError("401 invalid api key")
    monkeypatch.setattr(agent.litellm, "acompletion", broken)
    store = Store(tmp_path / "chats.sqlite")
    chat = store.create_chat()

    async def run():
        await agent.start_turn(store, chat["id"], "hello", entry["id"])
        await agent._runs[chat["id"]].task

    asyncio.run(run())
    last = store.messages(chat["id"])[-1]
    assert last["_error"] and "invalid api key" in last["content"]
    assert not agent.is_running(chat["id"])
