import pytest
import agent
import model_catalog
from store import ChatStore


def test_build_style_optional_and_validated():
    entry = {"litellm_params": {"model": "openai/gpt-6-astra"}}
    assert "build_style" not in model_catalog.validate_options(entry, None)
    assert model_catalog.validate_options(entry, {"build_style": "sculpture"})["build_style"] == "sculpture"
    with pytest.raises(ValueError, match="build style"):
        model_catalog.validate_options(entry, {"build_style": "unknown"})


def test_sculpture_prompt_is_compact_and_keeps_normal_flow(tmp_path, monkeypatch):
    source = tmp_path / "toolkit"
    guide = source / "docs/agent/sculptures.md"
    guide.parent.mkdir(parents=True)
    guide.write_text("Use the checked voxel converter and normal publish_model flow.")
    monkeypatch.setattr(agent.toolkit, "root", lambda: source)
    monkeypatch.setattr(agent.toolkit, "instructions", lambda: "Base instructions")
    monkeypatch.setattr(agent.toolkit, "builder_guides", lambda: "Base guides")
    store = ChatStore(tmp_path / "chats", tmp_path / "output")
    chat = store.create_chat()
    original = agent.system_prompt(store, chat["id"])
    assert guide.read_text() not in original
    store.update_chat(chat["id"], options={"build_style": "sculpture"})
    sculpture = agent.system_prompt(store, chat["id"])
    assert sculpture == guide.read_text()
    assert original not in sculpture
    store.update_chat(chat["id"], options={"build_style": "parts"})
    assert agent.system_prompt(store, chat["id"]) == original


def test_missing_paired_toolkit_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.setattr(agent.toolkit, "root", lambda: tmp_path)
    monkeypatch.setattr(agent.toolkit, "instructions", lambda: "Base instructions")
    monkeypatch.setattr(agent.toolkit, "builder_guides", lambda: "Base guides")
    store = ChatStore(tmp_path / "chats", tmp_path / "output")
    chat = store.create_chat()
    store.update_chat(chat["id"], options={"build_style": "sculpture"})
    with pytest.raises(ValueError, match="paired"):
        agent.system_prompt(store, chat["id"])


def test_sculpture_tools_and_turn_limit_preserve_permissions():
    names = lambda options: {t["function"]["name"] for t in agent.available_tools(options)}
    options = {"build_style": "sculpture", "mode": "agent", "permissions": "full"}
    assert names(options) == {"submit_brick_design", "accept_design"}
    assert agent.step_limit(options) == 6
    assert agent.step_limit({"mode": "agent"}) == agent.MAX_STEPS
    assert "submit_brick_design" not in names({"mode": "agent"})
    for key, value in (("mode", "plan"), ("permissions", "read_only")):
        assert names({**options, key: value}) == agent.READ_TOOLS


def test_sculpture_uses_existing_publish_download_and_step_flow():
    import asyncio
    import json
    import settings
    import tools
    from fastapi.testclient import TestClient
    from main import app
    from store import get_store

    if not (settings.TOOLKIT_DIR / 'docs/agent/sculptures.md').exists():
        pytest.skip('Requires the paired sculpture toolkit')
    import os
    os.chmod(settings.DATA_DIR.parent, 0o755)
    store = get_store()
    chat = store.create_chat()
    store.update_chat(chat['id'], options={'build_style': 'sculpture'})
    prompt = agent.system_prompt(store, chat['id'])
    assert 'Do not add a display base, stand, plinth, or ground plate' in prompt
    assert 'three failed design attempts and one visual review' in prompt
    ctx = tools.ToolContext(chat['id'], store, lambda *_: None)
    async def build():
        preview = await tools.t_submit_brick_design(ctx, grid={'width': 4, 'depth': 4, 'layers': 4},
            shapes=[{'shape': 'box', 'x': [0,3], 'y': [0,3], 'z': [0,3], 'color': 4}], title='Test sculpture')
        assert preview.images and 'preview_brick_count' in preview.content, preview.content
        published = await tools.t_accept_design(ctx)
        assert published.models and published.images, published.content
        report = json.loads((ctx.work_dir / 'sculpture-checks.json').read_text())
        assert report['brick_count'] > 0
        info = json.loads(published.content)
        assert info['checks_passed'], published.content
        return info, report
    info, report = asyncio.run(build())
    response = TestClient(app).get(info['model_url'])
    assert response.status_code == 200
    assert response.text.count('0 STEP') == report['step_count']
    assert 'Test sculpture' in response.text


@pytest.mark.parametrize("has_best,repair_succeeds", [(True, False), (False, True), (False, False)])
def test_failed_design_limit_keeps_good_design_or_repairs_last_attempt(tmp_path, monkeypatch, has_best, repair_succeeds):
    import asyncio
    import json
    import tools
    from sandbox import RunResult

    store = ChatStore(tmp_path / "chats", tmp_path / "output")
    chat = store.create_chat()
    ctx = tools.ToolContext(chat["id"], store, lambda *_: None)
    ctx.sculpture["failures"] = 2
    previous = {"voxels": "earlier.voxels.json", "title": "Earlier design"}
    if has_best:
        ctx.sculpture["best"] = previous
    calls = []
    async def command(ctx, argv, timeout):
        calls.append(argv)
        report = ctx.work_dir / "sculpture-1.preview.json"
        report.write_text(json.dumps({"checks_passed": repair_succeeds and "--repair" in argv, "error": "Cannot connect"}))
        return RunResult(0 if "--repair" in argv else 2, "", "", False, 0.01)
    async def accept(ctx):
        return tools.ToolResult("Accepted the best design")
    monkeypatch.setattr(tools, "run_command", command)
    monkeypatch.setattr(tools, "t_accept_design", accept)
    if not has_best and not repair_succeeds:
        async def attempts():
            with pytest.raises(tools.ToolError):
                await tools.t_submit_brick_design(ctx, {"width": 4, "depth": 4, "layers": 4}, [])
            result = await tools.dispatch(ctx, "submit_brick_design", {"grid": {}, "shapes": []})
            assert "three failed attempts" in result.content
        asyncio.run(attempts())
        assert len(calls) == 2  # no new preflight after terminal repair failure
        return
    result = asyncio.run(tools.t_submit_brick_design(ctx, {"width": 4, "depth": 4, "layers": 4}, []))
    assert result.content == "Accepted the best design"
    if has_best:
        assert ctx.sculpture["best"] == previous
        assert len(calls) == 1
    else:
        assert "--repair" in calls[-1] and len(calls) == 2
        assert ctx.sculpture["best"]["voxels"] == "sculpture-1.voxels.json"


def test_parallel_design_operation_is_rejected_without_running_conversion(tmp_path, monkeypatch):
    import asyncio
    import tools
    store = ChatStore(tmp_path / "chats", tmp_path / "output")
    chat = store.create_chat()
    ctx = tools.ToolContext(chat["id"], store, lambda *_: None)
    ctx.sculpture["busy"] = True
    result = asyncio.run(tools.dispatch(ctx, "accept_design", {}))
    assert result.content.startswith("Error: A sculpture operation is already running")
    assert ctx.sculpture["busy"]  # the first operation still owns the guard
