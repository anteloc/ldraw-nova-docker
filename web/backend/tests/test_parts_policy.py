import asyncio
import json
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agent
import main
import parts_policy
import settings
import tools
from parts_catalog import PartsUnavailable
from store import ChatStore

CATALOG = 'part_id,color_id,name,max_quantity\n3001,4,Brick 2 x 4,4\n'
MODEL = b'1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n'


@pytest.fixture
def configured(tmp_path, monkeypatch):
    policy = parts_policy.ChatPartsPolicy(tmp_path / 'protected')
    store = ChatStore(tmp_path / 'chats', tmp_path / 'output')
    chat_id = store.create_chat()['id']
    policy.configure(store, chat_id, CATALOG)
    monkeypatch.setattr(parts_policy, 'policy', policy)
    monkeypatch.setattr(parts_policy.sandbox, 'give_to_agent', lambda path: None)
    return policy, store, chat_id


def test_reference_cannot_change_authority_and_symlinks_are_replaced(configured, tmp_path):
    policy, store, chat_id = configured
    reference = store.work_dir(chat_id) / 'allowed-parts.csv'
    reference.write_text(CATALOG.replace('3001,4', '3001,0'))
    assert policy.load(chat_id).search('3001', 4)['total'] == 1
    assert policy.path(chat_id).stat().st_mode & 0o777 == 0o600
    reference.unlink()
    victim = tmp_path / 'keep'; victim.write_text('keep')
    reference.symlink_to(victim)
    policy.prepare(store, chat_id)
    assert victim.read_text() == 'keep'
    assert not reference.is_symlink()
    with pytest.raises(ValueError):
        policy.path('../escape')


def test_invalid_replacement_preserves_the_palette(configured):
    policy, store, chat_id = configured
    with pytest.raises(ValueError):
        policy.configure(store, chat_id, "invalid")
    assert policy.load(chat_id).search(color_id=4)["total"] == 1


def test_no_palette_leaves_normal_nova_unrestricted(tmp_path):
    policy = parts_policy.ChatPartsPolicy(tmp_path / 'config')
    store = SimpleNamespace(work_dir=lambda chat: tmp_path / chat)
    reference = tmp_path / "chat" / "allowed-parts.csv"
    reference.parent.mkdir()
    reference.write_text("User file")
    assert policy.prepare(store, 'chat') is False
    assert reference.read_text() == "User file"
    assert policy.validate_model('chat', MODEL) is None


def test_external_prices_are_not_stored_or_exposed(configured):
    policy, store, chat_id = configured
    source = 'part_id,color_id,unit_price,weight_kg,supplier_color\n3001,4,0.15,0.00219,010\n'
    policy.configure(store, chat_id, source)
    policy.prepare(store, chat_id)
    for path in (policy.path(chat_id), store.work_dir(chat_id) / 'allowed-parts.csv'):
        assert 'unit_price' not in path.read_text()
        assert '0.00219' not in path.read_text()
        assert 'supplier_color' not in path.read_text()
    assert 'unit_price' not in policy.load(chat_id).search()['parts'][0]


def test_shared_agent_prompt_and_tools_include_policy(configured, monkeypatch):
    _, store, chat_id = configured
    monkeypatch.setattr(agent.toolkit, 'instructions', lambda: 'instructions')
    monkeypatch.setattr(agent.toolkit, 'builder_guides', lambda: 'guides')
    assert 'MANDATORY PARTS POLICY' in agent.system_prompt(store, chat_id)
    assert {'list_allowed_parts', 'check_model_parts'} <= set(tools.TOOLS)
    names = {schema["function"]["name"] for schema in agent.available_tools({"permissions": "read_only"})}
    assert {"list_allowed_parts", "check_model_parts"} <= names


def test_publication_gate_runs_before_toolkit_or_model_storage(configured, monkeypatch):
    _, store, chat_id = configured
    ctx = tools.ToolContext(chat_id=chat_id, store=store, emit=lambda *args: None)
    model = store.work_dir(chat_id) / 'model.mpd'; model.write_bytes(MODEL)
    monkeypatch.setattr(parts_policy, 'expanded_inventory', lambda *args: {('3001', 0): 1})
    async def must_not_run(*args, **kwargs):
        raise AssertionError('Toolkit called before inventory validation')
    monkeypatch.setattr(tools, 'run_command', must_not_run)
    result = asyncio.run(tools.dispatch(ctx, 'publish_model', {'path': str(model)}))
    assert 'blocked publication' in result.content and not result.models
    assert not store.models(chat_id)
    check = asyncio.run(tools.dispatch(ctx, 'check_model_parts', {'path': str(model)}))
    assert json.loads(check.content)['valid'] is False
    monkeypatch.setattr(parts_policy, 'expanded_inventory', lambda *args: {('3001', 4): 1})
    check = asyncio.run(tools.dispatch(ctx, 'check_model_parts', {'path': str(model)}))
    assert json.loads(check.content) == {'valid': True, 'physical_parts': 1}
    search = asyncio.run(tools.dispatch(ctx, 'list_allowed_parts', {'query': '3001', 'limit': 1}))
    assert json.loads(search.content)['total'] == 1
    bad = asyncio.run(tools.dispatch(ctx, 'list_allowed_parts', {'limit': 1000}))
    assert 'limit between' in bad.content


def test_native_palette_endpoint_preserves_chat_and_running_boundaries(configured, monkeypatch):
    _, store, chat_id = configured
    monkeypatch.setattr(main, 'get_store', lambda: store)
    client = TestClient(main.app)
    endpoint = '/api/chats/' + chat_id + '/parts-palette'
    assert client.put(endpoint, json={'csv': CATALOG}).json()['allowed_combinations'] == 1
    assert client.put('/api/chats/missing/parts-palette', json={'csv': CATALOG}).status_code == 404
    assert client.put(endpoint, json={'csv': 'invalid'}).status_code == 400
    monkeypatch.setattr(agent, 'is_running', lambda chat: True)
    assert client.put(endpoint, json={'csv': CATALOG}).status_code == 409
    assert client.put(endpoint, headers={'Origin': 'https://other.example'}, json={'csv': CATALOG}).status_code == 403


def test_new_chat_upload_is_validated_before_creation_and_persisted(configured, monkeypatch):
    policy, store, _ = configured
    monkeypatch.setattr(main, 'get_store', lambda: store)
    client = TestClient(main.app)
    before = len(store.list_chats())
    assert client.post('/api/chats', json={'parts_palette_csv': 'invalid'}).status_code == 400
    assert len(store.list_chats()) == before
    response = client.post('/api/chats', json={'parts_palette_csv': CATALOG})
    assert response.status_code == 200
    chat = response.json()['id']
    assert policy.load(chat).parts[('3001', 4)].max_quantity == 4
    assert client.get(f'/api/chats/{chat}/parts-palette').json()['allowed_combinations'] == 1
    assert client.get('/api/chats/missing/parts-palette').status_code == 404


def test_clear_removes_palette_and_cannot_modify_a_running_chat(configured, monkeypatch):
    policy, store, chat = configured
    monkeypatch.setattr(main, 'get_store', lambda: store)
    client = TestClient(main.app)
    endpoint = f'/api/chats/{chat}/parts-palette'
    monkeypatch.setattr(agent, 'is_running', lambda _: True)
    assert client.delete(endpoint).status_code == 409
    assert policy.load(chat) is not None
    monkeypatch.setattr(agent, 'is_running', lambda _: False)
    assert client.delete(endpoint).json()['allowed_combinations'] is None
    assert policy.load(chat) is None
    assert not (store.work_dir(chat) / 'allowed-parts.csv').exists()


def test_validate_and_example_do_not_change_a_chat_palette(configured):
    policy, _, chat = configured
    client = TestClient(main.app)
    assert client.post('/api/parts-palette/validate', json={'csv': CATALOG}).json()['allowed_combinations'] == 1
    assert client.post('/api/parts-palette/validate', json={'csv': 'invalid'}).status_code == 400
    assert policy.load(chat).search(color_id=4)['total'] == 1
    example = client.get('/api/parts-palette/example')
    assert example.headers['content-type'].startswith('text/csv')
    assert 'part_id,color_id,max_quantity' in example.text


def test_selection_persists_without_losing_palette_and_controls_publication(configured, monkeypatch):
    policy, store, chat = configured
    monkeypatch.setattr(main, 'get_store', lambda: store)
    monkeypatch.setattr(parts_policy, 'expanded_inventory', lambda *args: {('3001', 0): 1})
    client = TestClient(main.app)
    endpoint = '/api/chats/' + chat + '/parts-palette'
    with pytest.raises(PartsUnavailable):
        policy.validate_model(chat, MODEL)
    disabled = client.patch(endpoint, json={'enabled': False})
    assert disabled.status_code == 200
    assert disabled.json()['enabled'] is False
    assert disabled.json()['allowed_combinations'] == 1
    assert policy.prepare(store, chat) is False
    assert not (store.work_dir(chat) / 'allowed-parts.csv').exists()
    assert policy.validate_model(chat, MODEL) is None
    reloaded = parts_policy.ChatPartsPolicy(policy.root.parent)
    assert reloaded.info(chat)['enabled'] is False
    assert reloaded.available(chat).search()['total'] == 1
    assert client.patch(endpoint, json={'enabled': True}).json()['enabled'] is True
    assert policy.prepare(store, chat)
    with pytest.raises(PartsUnavailable):
        policy.validate_model(chat, MODEL)
    monkeypatch.setattr(agent, 'is_running', lambda chat: True)
    assert client.patch(endpoint, json={'enabled': False}).status_code == 409
    assert client.delete(endpoint).status_code == 409
    assert policy.info(chat)['enabled'] is True


def test_new_chat_can_keep_an_uploaded_palette_disabled(configured, monkeypatch):
    policy, store, _ = configured
    monkeypatch.setattr(main, 'get_store', lambda: store)
    client = TestClient(main.app)
    chat = client.post('/api/chats', json={'parts_palette_csv': CATALOG, 'parts_palette_enabled': False}).json()['id']
    assert policy.info(chat)['allowed_combinations'] == 1
    assert policy.info(chat)['enabled'] is False
    assert policy.validate_model(chat, MODEL) is None
    assert client.patch('/api/chats/' + chat + '/parts-palette', json={'enabled': True}).status_code == 200
    empty = store.create_chat()['id']
    assert client.patch('/api/chats/' + empty + '/parts-palette', json={'enabled': True}).status_code == 400


def test_defaults_freeze_per_chat_and_invalid_catalog_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(parts_policy.sandbox, 'give_to_agent', lambda path: None)
    default = tmp_path / 'default.csv'; default.write_text(CATALOG)
    policy = parts_policy.ChatPartsPolicy(tmp_path / 'protected', default)
    store = SimpleNamespace(work_dir=lambda chat: tmp_path / chat)
    assert policy.prepare(store, 'chat')
    default.write_text(CATALOG.replace('3001,4', '3001,0'))
    assert policy.load('chat').search(color_id=4)['total'] == 1
    assert policy.load('other').search(color_id=0)['total'] == 1
    with pytest.raises(ValueError):
        policy.configure(store, 'chat', 'invalid')
    assert policy.load('chat').search(color_id=4)['total'] == 1


def test_server_configuration_selects_an_external_palette_only(monkeypatch):
    monkeypatch.delenv('NOVA_PARTS_PALETTE', raising=False)
    monkeypatch.delenv('NOVA_PARTS_CATALOG', raising=False)
    assert parts_policy.default_palette_path() is None
    monkeypatch.setenv('NOVA_PARTS_PALETTE', '/config/my-parts.csv')
    assert parts_policy.default_palette_path() == Path('/config/my-parts.csv')
    monkeypatch.setenv('NOVA_PARTS_PALETTE', 'relative.csv')
    with pytest.raises(ValueError):
        parts_policy.default_palette_path()
    monkeypatch.delenv('NOVA_PARTS_PALETTE')
    monkeypatch.setenv('NOVA_PARTS_CATALOG', '/config/legacy.csv')
    assert parts_policy.default_palette_path() == Path('/config/legacy.csv')


def test_disabling_and_clearing_default_palette(tmp_path, monkeypatch):
    monkeypatch.setattr(parts_policy.sandbox, 'give_to_agent', lambda path: None)
    default = tmp_path / 'default.csv'
    default.write_text(CATALOG)
    policy = parts_policy.ChatPartsPolicy(tmp_path / 'protected', default)
    store = SimpleNamespace(work_dir=lambda chat: tmp_path / chat)
    policy.prepare(store, 'chat')
    policy.set_enabled(store, 'chat', False)
    assert policy.validate_model('chat', MODEL) is None
    assert policy.info('chat') == {'allowed_combinations': 1, 'enabled': False}
    policy.set_enabled(store, 'chat', True)
    assert policy.prepare(store, 'chat')
    policy.configure(store, 'chat', CATALOG.replace('3001,4', '3001,0'))
    policy.clear(store, 'chat')
    assert policy.load('chat').search(color_id=4)['total'] == 1


def test_legacy_catalog_endpoint_preserves_contract_and_boundaries(configured, monkeypatch):
    policy, store, chat = configured
    monkeypatch.setattr(main, 'get_store', lambda: store)
    client = TestClient(main.app)
    endpoint = f'/api/chats/{chat}/parts-catalog'
    assert client.put(endpoint, json={'csv': CATALOG}).json() == {
        'parts_catalog_version': 1, 'allowed_combinations': 1}
    assert client.put(endpoint, json={'csv': 'invalid'}).status_code == 400
    assert policy.load(chat).search(color_id=4)['total'] == 1
    assert client.put('/api/chats/missing/parts-catalog', json={'csv': CATALOG}).status_code == 404
    monkeypatch.setattr(agent, 'is_running', lambda _: True)
    assert client.put(endpoint, json={'csv': CATALOG}).status_code == 409
    assert client.put(endpoint, headers={'Origin': 'https://other.example'}, json={'csv': CATALOG}).status_code == 403
