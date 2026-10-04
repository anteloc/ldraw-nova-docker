"""Integration with the real sibling toolkit, library, CLI and renderer."""
import asyncio
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agent
import environment_config
import inference
import sandbox
import settings
import toolkit
import tools
from main import app
from store import ChatStore, get_store


@pytest.fixture
def ctx():
    # Match /data's traversable ancestors while /config remains private.
    os.chmod(settings.DATA_DIR.parent, 0o755)
    store = get_store()
    chat = store.create_chat()
    return tools.ToolContext(chat["id"], store, lambda *_: None)


def test_workspace_is_standalone_layout_with_chat_local_output(ctx):
    other = ctx.store.create_chat()
    cwd = toolkit.workspace(ctx.store, ctx.chat_id)
    cwd2 = toolkit.workspace(ctx.store, other["id"])
    assert (cwd / "output").resolve() == ctx.work_dir.resolve()
    assert (cwd2 / "output").resolve() != (cwd / "output").resolve()
    assert (cwd / "data/ldraw-info.db").resolve() == settings.TOOLKIT_DIR / "data/ldraw-info.db"
    assert tools.resolve_path(ctx, "docs/agent/geometry.md").is_file()
    assert tools.resolve_path(ctx, "output/plan.json", write=True) == ctx.work_dir / "plan.json"
    with pytest.raises(tools.ToolError):
        tools.resolve_path(ctx, str(settings.TOOLKIT_DIR / "instructions.md"), write=True)
    (ctx.work_dir / "escape").symlink_to(settings.TOOLKIT_DIR)
    with pytest.raises(tools.ToolError):
        tools.resolve_path(ctx, "output/escape/instructions.md", write=True)
    prompt = agent.system_prompt(ctx.store, ctx.chat_id)
    assert toolkit.instructions() in prompt
    for path in toolkit.BUILDER_GUIDES:
        complete = (settings.TOOLKIT_DIR / path).read_text()
        assert complete in prompt
        assert prompt.index(toolkit.instructions()) < prompt.index(complete)
    assert "20-80" not in prompt
    assert "save_model" not in {s["function"]["name"] for s in tools.TOOL_SCHEMAS}


@pytest.mark.parametrize("many_steps", [False, True])
def test_real_doctor_build_publish_review_bom_and_download(ctx, many_steps):
    events = []
    ctx.emit = lambda event, data: events.append((event, data))

    async def run():
        doctor = await tools.run_command(ctx, ["./ldraw-agent", "doctor"], 60)
        assert doctor.exit_code == 0, doctor.as_text()
        info = json.loads(doctor.stdout)
        assert info["library_present"] and all(info["tools"].values())
        result = await tools.t_run_toolkit(ctx, ["build", "examples/bridge.plan.json", "--output", "output/bridge.mpd",
                                                "--report", "output/build.json"])
        assert "exit code 0" in result.content, result.content
        original = (ctx.work_dir / "bridge.mpd").read_bytes()
        if many_steps:
            rendered = await tools.t_run_toolkit(ctx, ["render", "output/bridge.mpd", "--outdir",
                                                      "output/reference", "--views", "home"])
            assert "exit code 0" in rendered.content, rendered.content
            reference = (ctx.work_dir / "reference/home.png").read_bytes()
            original = original.replace(b"\n1 ", b"\n" + b"0 STEP\n" * 300 + b"1 ", 1)
            (ctx.work_dir / "bridge.mpd").write_bytes(original)
        published = await tools.t_publish_model(ctx, "output/bridge.mpd", "Integration bridge")
        assert len(published.models) == 1, published.content
        info = json.loads(published.content)
        assert info["checks_passed"] and info["physical_validity"] == "not_proven"
        path = ctx.store.resolve(ctx.chat_id, published.models[0]["model"])
        assert path.read_bytes() == original  # no legacy sanitizer/serializer
        assert path.with_suffix(".png").stat().st_size > 1000
        if many_steps:
            assert path.with_suffix(".png").read_bytes() == reference
        assert path.with_suffix(".csv").stat().st_size > 50
        viewed = await tools.t_view_image(ctx, str(path.with_suffix(".png")))
        assert viewed.images and viewed.images[0].read_bytes().startswith(b"\x89PNG")
        comparison = await tools.t_run_toolkit(ctx, ["compare-bom", "output/bridge.mpd", "--csv", str(path.with_suffix(".csv")),
                                                    "--report", "output/bom-comparison.json"])
        assert "exit code 0" in comparison.content, comparison.content
        return info

    info = asyncio.run(run())
    assert any(e == "tool_output" for e, _ in events)
    assert any(e == "model" for e, _ in events)
    client = TestClient(app)
    assert client.get(info["validation"]).status_code == 200
    assert client.get(info["model_url"]).status_code == 200
    response = client.get(f"/api/chats/{ctx.chat_id}")
    [model] = response.json()["models"].values()
    assert info["card_url"] == f"/chat/{ctx.chat_id}#model-{model['id']}"
    assert info["viewer_url"].startswith("/viewer/viewer.html?model=%2Ffiles%2Fgenerated%2F")
    assert client.get(info["download_url"]).headers["content-disposition"].startswith("attachment")
    assert model["model_url"] == info["model_url"] and model["image_url"] and model["bom_url"]
    assert model["parts"] == 5
    assert "instructions.md" in asyncio.run(tools.t_list_files(ctx)).content


def test_key_overrides_only_typesafe_reach_tools_and_output_is_redacted(ctx, monkeypatch):
    monkeypatch.setattr(environment_config, "snapshot", lambda: {"TYPESAFE_API_KEY": "jev-test-private", "OPENAI_API_KEY": "provider-private"})
    events = []
    ctx.emit = lambda event, data: events.append(data)
    result = asyncio.run(tools.t_run_python(ctx, "import os\nprint(os.environ.get('TYPESAFE_API_KEY'))\nprint('provider-present', 'OPENAI_API_KEY' in os.environ)\nimport ldraw_tools, ldraw\nprint(ldraw.__file__)"))
    assert "exit code 0" in result.content, result.content
    assert "[redacted]" in result.content and "provider-present False" in result.content
    assert "jev-test-private" not in result.content + json.dumps(events)
    assert "site-packages/ldraw" in result.content


def test_toolkit_library_override_and_writable_cache(ctx, monkeypatch):
    monkeypatch.setattr(environment_config, "snapshot", lambda: {"LDRAW_DIR": "/custom/library"})
    env = toolkit.environment()
    assert env["LDRAW_DIR"] == "/custom/library"
    assert env["XDG_CACHE_HOME"] == str(settings.TOOLKIT_DIR / ".cache")
    result = asyncio.run(sandbox.run(["test", "-w", env["XDG_CACHE_HOME"]], ctx.work_dir, 30))
    assert result.exit_code == 0


def test_artifacts_reject_escape_and_force_download(ctx):
    (ctx.work_dir / "report.json").write_text('{"complete":true}')
    (ctx.work_dir / ".private").write_text("hidden")
    (ctx.work_dir / "outside").symlink_to(settings.TOOLKIT_DIR / "instructions.md")
    client = TestClient(app)
    base = f"/api/chats/{ctx.chat_id}/artifacts/"
    response = client.get(base + "report.json")
    assert response.status_code == 200 and "attachment" in response.headers["content-disposition"]
    assert "sandbox" in response.headers["content-security-policy"]
    for path in (".private", "outside", "..%2F..%2Fconfig%2Fmodels.json"):
        assert client.get(base + path).status_code == 404


def test_progress_reconnect_retains_output_and_stalled_provider_heartbeat(ctx):
    async def check():
        run = agent.Run(ctx.chat_id)
        run.task = asyncio.create_task(asyncio.sleep(60))
        agent._runs[ctx.chat_id] = run
        info = {"id": "cmd", "name": "run_shell", "arguments": "{}"}
        run.tools_running["cmd"] = info
        run.emit("tool_start", info)
        run.emit("tool_output", {"id": "cmd", "delta": "preparing geometry\n"})
        stream = agent.subscribe(ctx.chat_id)
        event, data = await anext(stream)
        assert event == "snapshot" and data["tools"][0]["output"] == "preparing geometry\n"
        assert data["tools"][0]["started_at"]
        event, data = await asyncio.wait_for(anext(stream), 7)
        assert event == "activity" and data["started_at"]
        await stream.aclose()
        run.task.cancel()
        await asyncio.gather(run.task, return_exceptions=True)
    asyncio.run(check())


def test_long_build_context_keeps_latest_complete_rounds(monkeypatch):
    monkeypatch.setattr(inference.litellm, "token_counter", lambda **kw: len(json.dumps(kw["messages"])))
    messages = [{"role": "system", "content": "instructions and current notes"},
                {"role": "user", "content": "Build the requested detailed model", "_turn_start": True}]
    for i in range(8):
        messages += [{"role": "assistant", "content": None, "tool_calls": [{"id": str(i)}]},
                     {"role": "tool", "tool_call_id": str(i), "content": "report" * 500}]
    bounded, removed = inference.bounded_history(messages, "fake", 12000)
    assert removed and bounded[1]["content"] == messages[1]["content"]
    assert bounded[-4:] == messages[-4:]
    calls = {c["id"] for m in bounded for c in m.get("tool_calls", [])}
    assert {m["tool_call_id"] for m in bounded if m["role"] == "tool"} == calls
