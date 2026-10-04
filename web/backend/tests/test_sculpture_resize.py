import hashlib
import json
import os

from fastapi.testclient import TestClient
import pytest

from main import app
import sculpture
import settings
import tools
from test_sculpture_editor import saved
from test_glb_import import cube_glb, upload


def bind_mesh(model):
    source=model.with_suffix('.source.glb');source.write_bytes(cube_glb())
    marker=model.with_suffix('.sculpture.json')
    meta=json.loads(marker.read_text());meta['source_glb_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    marker.write_text(json.dumps(meta))
    return source


def test_mesh_source_is_hash_bound_and_rejects_symlinks(tmp_path):
    model,_=saved('resize-source.mpd');source=bind_mesh(model)
    assert sculpture.mesh_source(model)==source
    assert sculpture.read(model)['resize_source']=='mesh'
    source.write_bytes(b'changed source')
    assert sculpture.mesh_source(model) is None
    assert sculpture.read(model)['resize_source']=='voxels'
    source=bind_mesh(model);copy=tmp_path/'mesh.glb';copy.write_bytes(source.read_bytes())
    source.unlink();source.symlink_to(copy)
    assert sculpture.mesh_source(model) is None
    source.unlink()


@pytest.mark.parametrize('size',[0,7,97,True,16.5,None])
def test_invalid_resize_never_runs_converter(monkeypatch,size):
    model,marker=saved()
    async def unexpected(*a,**k):pytest.fail('Invalid size reached conversion')
    monkeypatch.setattr(tools,'t_run_toolkit',unexpected)
    response=TestClient(app).post('/api/models/'+model.name+'/sculpture/resize',json={'resolution':size,'revision':marker['model_sha256']})
    assert response.status_code==422


def test_unknown_stale_and_cross_origin_resize_are_rejected():
    model,meta=saved();client=TestClient(app);url='/api/models/'+model.name+'/sculpture/resize'
    assert client.post(url,json={'resolution':8,'revision':'stale'}).status_code==409
    assert client.post('/api/models/missing.mpd/sculpture/resize',json={'resolution':8,'revision':'x'}).status_code==404
    assert client.post(url,json={'resolution':8,'revision':meta['model_sha256']},headers={'Origin':'https://other.example'}).status_code==403


@pytest.mark.parametrize('mesh',[False,True])
def test_resize_uses_bound_source_and_failure_preserves_original(monkeypatch,mesh):
    model,meta=saved();original=model.read_bytes()
    source=bind_mesh(model) if mesh else None
    async def failed(ctx,args,**kwargs):
        assert args[0]==('glb-sculpture' if mesh else 'resize-sculpture')
        assert args[args.index('--resolution')+1]=='16'
        assert kwargs['timeout']==1800
        supplied=ctx.work_dir/args[1].split('/')[-1]
        if mesh:assert supplied.read_bytes()==source.read_bytes()
        else:assert json.loads(supplied.read_text())['voxels']==sculpture.read(model)['voxels']
        assert ctx.store.get_chat(ctx.chat_id)['options']['build_style']=='sculpture'
        return tools.ToolResult('failed')
    async def unexpected(*a,**k):pytest.fail('Unchecked resize published')
    monkeypatch.setattr(tools,'t_run_toolkit',failed);monkeypatch.setattr(tools,'t_publish_model',unexpected)
    response=TestClient(app).post('/api/models/'+model.name+'/sculpture/resize',json={'resolution':16,'revision':meta['model_sha256']})
    assert response.status_code==422 and model.read_bytes()==original


def test_resize_serializes_expensive_work(monkeypatch):
    import main
    class Busy:
        def locked(self):return True
    monkeypatch.setattr(main,'_sculpture_resize_lock',Busy())
    model,meta=saved()
    response=TestClient(app).post('/api/models/'+model.name+'/sculpture/resize',json={'resolution':8,'revision':meta['model_sha256']})
    assert response.status_code==429


def test_deleting_a_model_removes_retained_mesh():
    model,_=saved('resize-delete.mpd');source=bind_mesh(model)
    assert TestClient(app).delete('/api/models/'+model.name).status_code==200
    assert not source.exists()


def test_real_import_resize_recovers_mesh_detail_and_remains_editable():
    if not (settings.TOOLKIT_DIR/'ldraw_tools/sculpture/resize.py').is_file():pytest.skip('Requires the paired resize toolkit')
    os.chmod(settings.DATA_DIR.parent,0o755)
    client=TestClient(app)
    imported=upload(client);assert imported.status_code==200,imported.text
    first=imported.json()['model'];original=settings.GENERATED_DIR/first['file'];original_bytes=original.read_bytes()
    assert sculpture.mesh_source(original)
    for size in (10,8):
        current=client.get('/api/models/'+first['file']+'/sculpture').json()
        result=client.post('/api/models/'+first['file']+'/sculpture/resize',json={'resolution':size,'revision':current['revision']})
        assert result.status_code==200,result.text
        data=result.json();assert data['model']['file']!=first['file'] and data['model']['parts']==data['brick_count']
        assert data['resize_source']=='mesh'
        assert max(max(r[i] for r in data['voxels'])-min(r[i] for r in data['voxels'])+1 for i in range(3))==size
        target=settings.GENERATED_DIR/data['model']['file']
        assert sculpture.mesh_source(target).read_bytes()==cube_glb()
        assert client.get(data['model']['model_url']+'?download=1').content==target.read_bytes()
        report=json.loads(next((settings.OUTPUT_DIR/data['chat_id']).glob('*.checks.json')).read_text())
        assert report['checks_passed'] and report['stud_components']==1 and report['connected_instruction_prefixes']
        assert client.get('/api/models/'+target.name+'/sculpture').json()['revision']==data['revision']
        first=data['model']
    assert original.read_bytes()==original_bytes
