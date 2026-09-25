import json
from pathlib import Path

import pytest

import settings
from store import ChatStore


@pytest.fixture
def store() -> ChatStore:
    return ChatStore(settings.CHATS_DIR, settings.OUTPUT_DIR)


def test_chat_is_a_folder_with_a_sibling_work_folder(store: ChatStore):
    chat = store.create_chat()
    assert (settings.CHATS_DIR / chat["id"] / "chat.json").is_file()
    assert (settings.OUTPUT_DIR / chat["id"]).is_dir()
    assert store.get_chat(chat["id"])["title"] == "New chat"


def test_messages_are_jsonl_with_sequential_ids(store: ChatStore):
    chat = store.create_chat()
    assert store.add_message(chat["id"], {"role": "user", "content": "hi"}) == 1
    assert store.add_message(chat["id"], {"role": "assistant", "content": "hello", "_notice": True}) == 2
    lines = (settings.CHATS_DIR / chat["id"] / "messages.jsonl").read_text().splitlines()
    assert [json.loads(line)["content"] for line in lines] == ["hi", "hello"]
    assert [m["id"] for m in ChatStore(settings.CHATS_DIR, settings.OUTPUT_DIR).messages(chat["id"])] == [1, 2]
    # a fresh store continues the numbering
    assert ChatStore(settings.CHATS_DIR, settings.OUTPUT_DIR).add_message(chat["id"], {"role": "user", "content": "x"}) == 3


def test_models_are_relative_references_into_generated(store: ChatStore):
    chat = store.create_chat()
    model = settings.GENERATED_DIR / "thing-v1.mpd"
    ref = store.add_model(chat["id"], "Thing", model, warnings=[])
    assert ref["model"] == "../../generated/thing-v1.mpd"
    assert store.resolve(chat["id"], ref["model"]) == model


def test_delete_removes_chat_and_work_folder_but_not_models(store: ChatStore):
    chat = store.create_chat()
    settings.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    model = settings.GENERATED_DIR / "keep-me.mpd"
    model.write_text("0 FILE x\n")
    store.add_model(chat["id"], "Keep", model, warnings=[])
    (store.work_dir(chat["id"]) / "NOTES.md").write_text("plan")
    store.delete_chat(chat["id"])
    assert not (settings.CHATS_DIR / chat["id"]).exists()
    assert not (settings.OUTPUT_DIR / chat["id"]).exists()
    assert model.exists()


def test_rejects_path_like_chat_ids(store: ChatStore):
    for bad in ("../x", "a/b", "", ".hidden", "x" * 80):
        assert store.get_chat(bad) is None
        with pytest.raises(ValueError):
            store.chat_dir(bad)
