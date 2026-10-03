import hashlib
import json
import pytest
import sculpture
import settings
from fastapi.testclient import TestClient
from main import app, model_info


def saved(name='editor-test.mpd'):
    settings.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    model = settings.GENERATED_DIR / name
    model.write_bytes(b'0 FILE editor-test.ldr\r\n0 Test sculpture\r\n')
    voxels, marker = sculpture.siblings(model)
    voxels.write_text(json.dumps({'voxels': [[0,0,0,4],[0,0,1,4]]}))
    meta = {'version':1,'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),
            'voxel_sha256':hashlib.sha256(voxels.read_bytes()).hexdigest()}
    marker.write_text(json.dumps(meta))
    return model, meta


def test_revision_binding_and_ordinary_models():
    model, _ = saved()
    assert sculpture.read(model)['voxels'] == [[0,0,0,4],[0,0,1,4]]
    assert model_info(model)['sculpture']
    model.write_text('changed model')
    assert sculpture.read(model) is None
    assert not model_info(model)['sculpture']


def test_stale_voxel_data_and_symlinks_are_not_editable(tmp_path):
    model, _ = saved()
    voxels, marker = sculpture.siblings(model)
    voxels.write_text('{"voxels":[[0,0,0,1]]}')
    assert sculpture.read(model) is None
    model, _ = saved()
    target=tmp_path/'hidden'; target.write_text(voxels.read_text())
    voxels.unlink(); voxels.symlink_to(target)
    assert sculpture.read(model) is None
    voxels.unlink()


@pytest.mark.parametrize('rows',[[],[[0,0,0,16]],[[0,0,0,4],[0,0,0,1]],[[0,0,0,4],[96,0,0,4]],[[True,0,0,4]],[[0,0,0,4.1]]])
def test_invalid_edits(rows):
    with pytest.raises(ValueError): sculpture.validate_rows(rows)


def test_api_rejects_unknown_stale_and_invalid_without_modifying_original():
    client=TestClient(app)
    model, meta=saved()
    original=model.read_bytes()
    url='/api/models/'+model.name+'/sculpture'
    assert client.get(url).status_code==200
    assert client.get('/api/models/ordinary.mpd/sculpture').status_code==404
    assert client.post(url,json={'revision':'stale','voxels':[[0,0,0,4]]}).status_code==409
    for rows in [[],[[0,0,0,True]],[[0,0,0,4.1]],[[0,0,0,4],[97,0,0,4]]]:
        assert client.post(url,json={'revision':meta['model_sha256'],'voxels':rows}).status_code==422
    assert model.read_bytes()==original


def test_failed_conversion_keeps_original(monkeypatch):
    import tools
    model, meta=saved()
    original=model.read_bytes()
    async def failed(*args,**kwargs): return tools.ToolResult('failed')
    monkeypatch.setattr(tools,'t_run_toolkit',failed)
    response=TestClient(app).post('/api/models/'+model.name+'/sculpture',json={'revision':meta['model_sha256'],'voxels':[[0,0,0,4]]})
    assert response.status_code==422
    assert model.read_bytes()==original


def test_palette_reads_official_ldraw_spacing(tmp_path, monkeypatch):
    library=tmp_path/'library'; library.mkdir()
    (library/'LDConfig.ldr').write_text('0 !COLOUR Black    CODE  0  VALUE #1B2A34 EDGE #808080\n0 !COLOUR Main_Colour CODE 16 VALUE #FFFF80 EDGE #333333\n')
    monkeypatch.setattr(settings,'LDRAW_DIR',library)
    assert sculpture.palette()==[{'code':0,'name':'Black','hex':'#1B2A34'}]


def test_deleting_model_cleans_up_its_editable_artifacts():
    model, _ = saved('editor-delete.mpd')
    response = TestClient(app).delete('/api/models/'+model.name)
    assert response.status_code == 200
    assert all(not p.exists() for p in (model, *sculpture.siblings(model)))
