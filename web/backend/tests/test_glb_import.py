import hashlib
import json
import struct

from fastapi.testclient import TestClient
import pytest
import settings
import sculpture
import tools
from main import app


def cube_glb():
    vertices = [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
    indices = [0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,2,3,7,2,7,6,1,2,6,1,6,5,3,0,4,3,4,7]
    binary = b''.join(struct.pack('<fff',*v) for v in vertices) + struct.pack('<36H',*indices)
    document = {'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0]}], 'nodes':[{'mesh':0}],
        'meshes':[{'primitives':[{'attributes':{'POSITION':0},'indices':1,'material':0}]}],
        'materials':[{'pbrMetallicRoughness':{'baseColorFactor':[0.77,0.16,0.1,1]}}],
        'buffers':[{'byteLength':len(binary)}],
        'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':96},{'buffer':0,'byteOffset':96,'byteLength':72}],
        'accessors':[{'bufferView':0,'componentType':5126,'count':8,'type':'VEC3','min':[-1,-1,-1],'max':[1,1,1]},
            {'bufferView':1,'componentType':5123,'count':36,'type':'SCALAR'}]}
    encoded = json.dumps(document).encode(); encoded += b' ' * (-len(encoded)%4)
    return struct.pack('<4sII',b'glTF',2,28+len(encoded)+len(binary)) + struct.pack('<II',len(encoded),0x4E4F534A)+encoded+struct.pack('<II',len(binary),0x004E4942)+binary


def upload(client, data=None, query='resolution=8&title=Imported%20cube', headers=None):
    return client.post('/api/models/import-glb?'+query, content=cube_glb() if data is None else data,
        headers={'Content-Type':'model/gltf-binary',**(headers or {})})


@pytest.mark.parametrize('query,data,headers,status',[
    ('resolution=49',None,None,422),('resolution=0',None,None,422),
    ('title=%0A',None,None,422),('title=',None,None,422),
    ('resolution=8',b'not a mesh',None,422),
    ('resolution=8',None,{'Content-Type':'text/plain'},415),
    ('resolution=8',b'x'*(16*1024*1024+1),None,413),
    ('resolution=8',None,{'Origin':'https://other.example'},403),
])
def test_invalid_upload_never_runs_converter(monkeypatch,query,data,headers,status):
    async def unexpected(*a,**k): pytest.fail('Invalid upload reached conversion')
    monkeypatch.setattr(tools,'t_run_toolkit',unexpected)
    assert upload(TestClient(app),data,query,headers).status_code == status


def test_reports_converter_failure_and_publishes_nothing(monkeypatch):
    async def failed(ctx,args,**kwargs):
        assert ctx.store.get_chat(ctx.chat_id)['options']['build_style']=='sculpture'
        path=ctx.work_dir/(args[-1].split('/')[-1])
        path.write_text(json.dumps({'checks_passed':False,'error':'Mesh cannot be connected at this resolution'}))
        return tools.ToolResult('failed')
    async def unexpected(*a,**k): pytest.fail('Unchecked model published')
    monkeypatch.setattr(tools,'t_run_toolkit',failed)
    monkeypatch.setattr(tools,'t_publish_model',unexpected)
    response=upload(TestClient(app))
    assert response.status_code==422
    assert 'cannot be connected' in response.json()['detail']


def test_only_one_glb_import_can_run(monkeypatch):
    import main
    class Busy:
        def locked(self): return True
    monkeypatch.setattr(main,'_glb_import_lock',Busy())
    assert upload(TestClient(app)).status_code==429


def test_import_publishes_revision_bound_editable_model():
    """Real GLB -> voxelize -> pack -> validate/render -> editor/download route."""
    import os
    if not (settings.TOOLKIT_DIR/'ldraw_tools/sculpture/glb_import.py').is_file():
        pytest.skip('Requires the paired GLB toolkit')
    os.chmod(settings.DATA_DIR.parent,0o755)
    client=TestClient(app)
    response=upload(client)
    assert response.status_code==200,response.text
    result=response.json()
    assert result['import']['voxelizer']=='trimesh-subdivide'
    assert result['import']['surface_voxels']>0
    assert result['model']['sculpture'] and result['model']['parts']>0
    model=settings.GENERATED_DIR/result['model']['file']
    data=client.get('/api/models/'+model.name+'/sculpture').json()
    assert len(data['voxels'])>=result['import']['surface_voxels']
    assert data['revision']==hashlib.sha256(model.read_bytes()).hexdigest()
    assert client.get(result['model']['model_url']+'?download=1').status_code==200
    checks=next((settings.OUTPUT_DIR/result['chat_id']).glob('*.checks.json'))
    report=json.loads(checks.read_text())
    assert report['checks_passed'] and report['stud_components']==1
    assert report['connected_instruction_prefixes']
    assert sculpture.read(model)['voxels']==data['voxels']
    chat=client.get('/api/chats/'+result['chat_id']).json()
    assert chat['chat']['options']['build_style']=='sculpture'
    assert 'Detail: 8 studs' in chat['messages'][0]['content']
    assert chat['messages'][-1]['_models']
