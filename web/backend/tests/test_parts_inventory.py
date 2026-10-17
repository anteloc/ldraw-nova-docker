from pathlib import Path
import pytest
import subprocess
import settings
from parts_policy import expanded_inventory
from parts_catalog import PartsCatalog, PartsUnavailable

MODEL = '0 FILE root.ldr\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 child.ldr\n0 FILE child.ldr\n1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n'


def model_inventory(source, library):
    return expanded_inventory(source.read_bytes(), settings.TOOLKIT_DIR, library)


def library():
    path = settings.LDRAW_DIR
    if not path.exists():
        pytest.skip('Real LDraw library available in the Nova image')
    return path


def test_real_hierarchy_colors_and_unknown_dependencies(tmp_path):
    source = tmp_path / 'model.mpd'; source.write_text(MODEL)
    inventory = model_inventory(source, library())
    assert inventory == {('3001', 4): 1}
    catalog = PartsCatalog.from_csv('part_id,color_id\n3001,4\n')
    catalog.validate(inventory)
    source.write_text(MODEL.replace('1 4 ', '1 0 '))
    with pytest.raises(PartsUnavailable):
        catalog.validate(model_inventory(source, library()))
    for reference in ('missing.ldr', 'missing.dat'):
        source.write_text(MODEL.replace('3001.dat', reference))
        with pytest.raises((ValueError, FileNotFoundError, KeyError, subprocess.SubprocessError)):
            model_inventory(source, library())


def test_real_parser_rejects_embedded_part_override(tmp_path):
    source = tmp_path / 'model.mpd'; source.write_text(MODEL + '0 FILE 3001.dat\n0 Fake\n')
    with pytest.raises(PartsUnavailable):
        model_inventory(source, library())


def test_geometry_changes_are_rejected_by_the_paired_checker(tmp_path):
    source = tmp_path / 'model.mpd'
    for matrix in ('2 0 0 0 1 0 0 0 1', '1 .1 0 0 1 0 0 0 1', '-1 0 0 0 1 0 0 0 1'):
        source.write_text(MODEL.replace('1 16 0 0 0 1 0 0 0 1 0 0 0 1', '1 16 0 0 0 ' + matrix))
        with pytest.raises((ValueError, subprocess.SubprocessError)):
            model_inventory(source, library())


@pytest.mark.parametrize('extension', ['csv', 'ldr', 'xml', 'io'])
def test_uploaded_palette_reaches_real_publication_gate(tmp_path, monkeypatch, extension):
    import asyncio
    import base64
    import io
    import json
    import zipfile
    from fastapi.testclient import TestClient
    import main
    import parts_policy
    import tools
    from store import ChatStore

    library()
    placement = b'1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n'
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('model.ldr', placement)
    data = {'csv': b'part_id,color_id,max_quantity\n3001,4,1\n', 'ldr': placement,
            'xml': b'<INVENTORY><ITEM><ITEMTYPE>P</ITEMTYPE><ITEMID>3001</ITEMID><COLOR>5</COLOR><MINQTY>1</MINQTY></ITEM></INVENTORY>',
            'io': archive.getvalue()}[extension]
    policy = parts_policy.ChatPartsPolicy(tmp_path / 'protected')
    settings.DATA_DIR.parent.chmod(0o755)
    store = ChatStore(settings.CHATS_DIR, settings.OUTPUT_DIR)
    monkeypatch.setattr(parts_policy, 'policy', policy)
    monkeypatch.setattr(main, 'get_store', lambda: store)
    client = TestClient(main.app)
    response = client.post('/api/parts-palette/import', json={
        'filename': 'parts.' + extension, 'data_base64': base64.b64encode(data).decode()})
    assert response.status_code == 200, response.text
    chat = client.post('/api/chats', json={'parts_palette_csv': response.json()['csv']}).json()['id']
    ctx = tools.ToolContext(chat_id=chat, store=store, emit=lambda *args: None)
    source = store.work_dir(chat) / 'candidate.ldr'
    source.write_bytes(placement)
    check = asyncio.run(tools.dispatch(ctx, 'check_model_parts', {'path': str(source)}))
    assert json.loads(check.content) == {'valid': True, 'physical_parts': 1}
    # Real expansion and publication checks: no mocked inventory or validator.
    for invalid in (placement.replace(b'1 4 ', b'1 0 '),
                    placement.replace(b'3001.dat', b'3003.dat'), placement * 2):
        source.write_bytes(invalid)
        rejected = asyncio.run(tools.dispatch(ctx, 'publish_model', {'path': str(source)}))
        assert 'blocked publication' in rejected.content
        assert store.models(chat) == []
    # Editing the agent's reference cannot override the protected inventory.
    (store.work_dir(chat) / 'allowed-parts.csv').write_text('part_id,color_id\n3001,0\n')
    with pytest.raises(PartsUnavailable):
        policy.validate_model(chat, placement.replace(b'1 4 ', b'1 0 '))

    source.write_bytes(b'0 FILE palette.ldr\n0 Palette test\n0 Name: palette.ldr\n'
                       b'0 Author: Tests\n0 !LDRAW_ORG Model\n' + placement + b'0 NOFILE\n')
    published = asyncio.run(tools.dispatch(ctx, 'publish_model', {'path': str(source), 'name': f'Palette {extension}'}))
    report = json.loads(published.content)
    assert report['checks_passed'], report
    assert report['parts_palette'] == report['parts_catalog'] == {'valid': True, 'physical_parts': 1}
    model = store.resolve(chat, published.models[0]['model'])
    assert model.read_bytes() == source.read_bytes()
    assert model.with_suffix('.png').stat().st_size > 1000
    comparison = asyncio.run(tools.t_run_toolkit(ctx, [
        'compare-bom', str(model), '--csv', str(model.with_suffix('.csv'))]))
    assert 'exit code 0' in comparison.content, comparison.content
