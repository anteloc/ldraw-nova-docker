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


def test_sculpture_prompt_is_explicit_and_keeps_normal_flow(tmp_path, monkeypatch):
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
    assert original in sculpture and guide.read_text() in sculpture
    store.update_chat(chat["id"], options={})
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
    assert 'fixed-seed color-constrained rectangular-brick packing' in prompt
    ctx = tools.ToolContext(chat['id'], store, lambda *_: None)
    design = {'grid': {'width': 4, 'depth': 4, 'layers': 4},
              'shapes': [{'shape': 'box', 'x': [0,3], 'y': [0,3], 'z': [0,3], 'color': 4}]}
    async def build():
        await tools.t_write_file(ctx, 'output/sculpture.design.json', json.dumps(design))
        built = await tools.t_run_toolkit(ctx, ['sculpture', 'output/sculpture.design.json',
            '--output', 'output/sculpture.mpd', '--report', 'output/sculpture-checks.json'])
        assert 'exit code 0' in built.content, built.content
        report = json.loads((ctx.work_dir / 'sculpture-checks.json').read_text())
        assert report['checks_passed'] and report['brick_count'] > 0
        published = await tools.t_publish_model(ctx, 'output/sculpture.mpd', 'Test sculpture')
        info = json.loads(published.content)
        assert info['checks_passed'], published.content
        return info, report
    info, report = asyncio.run(build())
    response = TestClient(app).get(info['model_url'])
    assert response.status_code == 200
    assert response.text.count('0 STEP') == report['step_count']
    assert 'Sculpture model' in response.text


def test_sculpture_uses_the_normal_tools_and_permissions():
    normal = {"mode": "agent", "permissions": "full"}
    assert agent.available_tools({**normal, "build_style": "sculpture"}) == agent.available_tools(normal)
    for key, value in (("mode", "plan"), ("permissions", "read_only")):
        names = {tool["function"]["name"] for tool in agent.available_tools(
            {**normal, "build_style": "sculpture", key: value})}
        assert names == agent.READ_TOOLS
