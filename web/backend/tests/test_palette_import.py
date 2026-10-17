import base64
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

import main
import parts_policy
from parts_catalog import PartsCatalog, PartsUnavailable
from store import ChatStore

MODEL = b'1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n'
XML = b'<INVENTORY><ITEM><ITEMTYPE>P</ITEMTYPE><ITEMID>3001</ITEMID><COLOR>5</COLOR><MINQTY>1</MINQTY></ITEM></INVENTORY>'


def archive():
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as zip_file:
        zip_file.writestr('model.ldr', MODEL)
    return output.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    policy = parts_policy.ChatPartsPolicy(tmp_path / 'protected')
    store = ChatStore(tmp_path / 'chats', tmp_path / 'output')
    monkeypatch.setattr(parts_policy, 'policy', policy)
    monkeypatch.setattr(main, 'get_store', lambda: store)
    monkeypatch.setattr(parts_policy.sandbox, 'give_to_agent', lambda _: None)
    return TestClient(main.app), store, policy


@pytest.mark.parametrize('filename,data', [
    ('parts.ldr', MODEL), ('parts.xml', XML), ('parts.io', archive()),
    ('parts.csv', b'part_id,color_id,max_quantity\n3001,4,1\n'),
    ('bom.csv', b'LdrawId,LDrawColorId,Qty\n3001.dat,4,1\n'),
])
def test_import_persists_for_new_and_existing_chats_and_enforces_publication(client, monkeypatch, filename, data):
    http, store, policy = client
    response = http.post('/api/parts-palette/import', json={
        'filename': filename, 'data_base64': base64.b64encode(data).decode()})
    assert response.status_code == 200, response.text
    assert store.list_chats() == []
    imported = response.json()
    assert imported['allowed_combinations'] == 1
    palette = PartsCatalog.from_csv(imported['csv'])
    assert palette.parts[('3001', 4)].max_quantity == 1
    chat = http.post('/api/chats', json={'parts_palette_csv': imported['csv']}).json()['id']
    endpoint = f'/api/chats/{chat}/parts-palette'
    assert http.put(endpoint, json={'csv': imported['csv']}).status_code == 200
    monkeypatch.setattr(parts_policy, 'expanded_inventory', lambda *args: {('3001', 4): 1})
    assert policy.validate_model(chat, MODEL)['valid']
    for inventory in ({('3001', 4): 2}, {('3001', 0): 1}, {('3005', 4): 1}):
        monkeypatch.setattr(parts_policy, 'expanded_inventory', lambda *args: inventory)
        with pytest.raises(PartsUnavailable):
            policy.validate_model(chat, MODEL)
    assert http.patch(endpoint, json={'enabled': False}).status_code == 200
    assert policy.validate_model(chat, MODEL) is None
    assert http.patch(endpoint, json={'enabled': True}).status_code == 200
    with pytest.raises(PartsUnavailable):
        policy.validate_model(chat, MODEL)


@pytest.mark.parametrize('filename,data', [
    ('bad.io', b'not zip'), ('bad.xml', b'<!DOCTYPE INVENTORY><INVENTORY/>'),
    ('bad.ldr', MODEL.replace(b'3001.dat', b'missing.ldr')), ('bad.txt', MODEL),
    ('bad.csv', b'part_id,color_id\n'), ('bad.csv', b'\xff'),
])
def test_failed_import_preserves_existing_palette_and_disabled_selection(client, filename, data):
    http, store, policy = client
    chat = store.create_chat()['id']
    policy.configure(store, chat, 'part_id,color_id\n3001,4\n')
    policy.set_enabled(store, chat, False)
    response = http.post('/api/parts-palette/import', json={
        'filename': filename, 'data_base64': base64.b64encode(data).decode()})
    assert response.status_code == 400
    assert policy.info(chat) == {'enabled': False, 'allowed_combinations': 1}
    assert len(store.list_chats()) == 1


def test_import_rejects_invalid_base64_and_cross_origin_requests(client):
    http, _, _ = client
    payload = {'filename': 'parts.ldr', 'data_base64': 'not base64!'}
    assert http.post('/api/parts-palette/import', json=payload).status_code == 400
    assert http.post('/api/parts-palette/import', json=payload, headers={
        'Origin': 'https://other.example'}).status_code == 403


def test_binary_upload_request_limit_accounts_for_base64(client):
    http, _, _ = client
    payload = {'filename': 'parts.ldr', 'data_base64': base64.b64encode(MODEL).decode()}
    # Keep the fixture small while testing the middleware's Content-Length branch.
    assert http.post('/api/parts-palette/import', json=payload,
        headers={'Content-Length': str(22 * 1024 * 1024)}).status_code == 200
    assert http.post('/api/parts-palette/import', json=payload,
        headers={'Content-Length': str(24 * 1024 * 1024)}).status_code == 413
