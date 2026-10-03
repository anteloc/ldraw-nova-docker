import assert from "node:assert/strict";
import test from "node:test";
import { Window } from "happy-dom";
const window = new Window();
Object.assign(globalThis,{window,document:window.document,HTMLElement:window.HTMLElement,Event:window.Event,
  MouseEvent:window.MouseEvent,File:window.File,IS_REACT_ACT_ENVIRONMENT:true});
const React=await import('react'); const {act}=React;
const {createRoot}=await import('react-dom/client');
const {MemoryRouter}=await import('react-router-dom');
const {AppContext}=await import('../src/context');
const {api}=await import('../src/api');
const {default:GlbImport,validateGlbFile}=await import('../src/components/GlbImport');
const {default:Models}=await import('../src/pages/Models');

test('file validation rejects the wrong format, incomplete and oversized uploads',()=>{
  assert.match(validateGlbFile(new File(['x'.repeat(20)],'cube.obj')),/glTF/);
  assert.match(validateGlbFile(new File([],'cube.glb')),/incomplete/);
  assert.match(validateGlbFile(new File([new Uint8Array(16*1024*1024+1)],'cube.glb')),/16 MB/);
  assert.equal(validateGlbFile(new File(['x'.repeat(20)],'cube.GLB')),'');
});

test('GLB request sends binary bytes with encoded name and resolution',async t=>{
  const file=new File(['x'.repeat(20)],'my cube.glb');
  t.mock.method(globalThis,'fetch',async (url:any,init:any)=>{
    assert.equal(url,'/api/models/import-glb?resolution=16&title=Red+%26+blue');
    assert.equal(init.body,file); assert.equal(init.headers['Content-Type'],'model/gltf-binary');
    return new Response('{}',{headers:{'Content-Type':'application/json'}});
  });
  await api.importGlb(file,16,'Red & blue');
});

test('upload retries failures, blocks dismissal while converting and hands the saved model to the editor',async t=>{
  const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
  const model:any={file:'cube-v1.mpd',description:'Cube',model_url:'/files/generated/cube-v1.mpd',parts:21};
  const edited:any[]=[];let closed=0,changed=0,attempts=0;
  const listener=()=>changed++;window.addEventListener('models-changed',listener);
  let finish:(value:any)=>void=()=>assert.fail('Not converting');
  t.mock.method(api,'importGlb',async (file:File,resolution:number,title:string)=>{
    assert.equal(file.name,'cube.glb');assert.equal(resolution,16);assert.equal(title,'cube');
    attempts++;
    if(attempts===1) throw new Error('Mesh needs a lower resolution');
    return new Promise(resolve=>{finish=resolve;});
  });
  try{
    await act(async()=>root.render(<AppContext.Provider value={{refreshChats(){},openViewer(){}} as any}><GlbImport onClose={()=>closed++} onEdit={m=>edited.push(m)} /></AppContext.Provider>));
    const dialog=document.querySelector('[aria-label="GLB to LEGO"]')!;
    const input=dialog.querySelector('input[type="file"]') as HTMLInputElement;
    Object.defineProperty(input,'files',{value:[new File(['x'.repeat(20)],'cube.glb')]});
    await act(async()=>input.dispatchEvent(new Event('change',{bubbles:true})));
    const detail=dialog.querySelector('select')!;
    await act(async()=>{detail.value='16';detail.dispatchEvent(new Event('change',{bubbles:true}));});
    const form=dialog.querySelector('form')!;
    await act(async()=>form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
    assert.match(dialog.querySelector('[role="alert"]')!.textContent!,/lower resolution/);
    await act(async()=>form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
    assert.equal((dialog.querySelector('[aria-label="Close import"]') as HTMLButtonElement).disabled,true);
    await act(async()=>document.dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape'})));
    assert.equal(closed,0);
    await act(async()=>finish({model,chat_id:'import',support_voxels:5,import:{surface_voxels:50,palette_colors:2,dimensions:[16,8,8]}}));
    assert.match(dialog.textContent!,/Added 5 support cells/);assert.equal(changed,1);
    await act(async()=>[...dialog.querySelectorAll('button')].find(b=>b.textContent==='Edit voxels')!.click());
    assert.deepEqual(edited,[model]);
  } finally {await act(async()=>root.unmount());host.remove();window.removeEventListener('models-changed',listener);}
});

test('import action is on My Models and absent from the bundled gallery',async t=>{
  t.mock.method(api,'models',async()=>({models:[],pending:0}));
  const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
  try{
    for(const collection of ['models','gallery'] as const){
      await act(async()=>root.render(<MemoryRouter><Models collection={collection}/></MemoryRouter>));
      assert.equal([...host.querySelectorAll('button')].some(b=>b.textContent==='Import GLB'),collection==='models');
    }
  } finally{await act(async()=>root.unmount());host.remove();}
});
