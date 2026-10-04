import assert from "node:assert/strict";
import { test } from "node:test";
import { editCells, type Cell } from "../src/sculpture/cells";
import { Window } from "happy-dom";

const cells: Cell[] = [[0,0,0,4],[0,0,1,4]];
test("face additions use integer brick layers and preserve all existing cells", () => {
  assert.deepEqual(editCells(cells,1,"add",1,[0,0,1]),[...cells,[0,0,2,1]]);
  assert.equal(editCells(cells,0,"add",1,[0,0,1]),cells);
  assert.deepEqual(editCells(cells,1,"add",1,[.9,.2,.1]),[...cells,[1,0,1,1]]);
});

test("paint and erase only the selected cell; orbit does not edit", () => {
  assert.deepEqual(editCells(cells,1,"paint",14,[]),[[0,0,0,4],[0,0,1,14]]);
  assert.deepEqual(editCells(cells,1,"erase",14,[]),[[0,0,0,4]]);
  assert.equal(editCells([cells[0]],0,"erase",14,[]).length,1);
  assert.equal(editCells(cells,1,"orbit",14,[]),cells);
});
test("editor refuses additions exceeding converter bounds", () => {
  const wide: Cell[] = [[0,0,0,4],[95,0,0,4]];
  assert.equal(editCells(wide,1,"add",4,[1,0,0]),wide);
});
const window = new Window({ url: "http://localhost/" });
Object.assign(globalThis,{window, document: window.document, HTMLElement: window.HTMLElement,
  Event: window.Event, MouseEvent: window.MouseEvent, IS_REACT_ACT_ENVIRONMENT: true});
const React = await import("react");
const {act} = React;
const {createRoot} = await import("react-dom/client");
const {MemoryRouter} = await import("react-router-dom");
const {AppContext} = await import("../src/context");
const {default: ModelCard} = await import("../src/components/ModelCard");
const {default: SculptureEditor} = await import("../src/components/SculptureEditor");
const {api} = await import("../src/api");
test("editor action appears only on eligible generated sculpture cards", async () => {
  const el = document.createElement('div'); document.body.append(el); const root=createRoot(el);
  const model: any = {file:'owl.mpd', model_url:'/files/generated/owl.mpd', image_url:null, description:'Owl', warnings:[], mtime:1};
  for (const [sculpture,gallery,expected] of [[false,false,false],[true,false,true],[true,true,false]]) {
    await act(async()=>root.render(<MemoryRouter><AppContext.Provider value={{openViewer(){}} as any}><ModelCard model={{...model,sculpture,gallery}} /></AppContext.Provider></MemoryRouter>));
    assert.equal(Array.from(el.querySelectorAll('button')).some(b=>b.textContent==='Sculpture editor'),expected);
  }
  await act(async()=>root.unmount()); el.remove();
});

test("saving displays the server's repaired cells and opens that saved model", async (t) => {
  const element = document.createElement('div'); document.body.append(element);
  const root = createRoot(element);
  const model: any = {file:'robot.mpd',description:'Robot'};
  const edited: Cell[] = [...cells,[1,0,1,4]];
  const repaired: Cell[] = [...edited,[1,0,0,4]];
  const updates: Cell[][] = [];
  const opened: any[] = [];
  let closed = false;
  let pick: (index: number, normal: number[]) => void = () => assert.fail('Scene not initialized');
  t.mock.method(api,'sculpture',async () => ({voxels:cells,revision:'original',palette:[]}));
  t.mock.method(api,'saveSculpture',async (file: string, voxels: Cell[], revision: string) => {
    assert.equal(file,'robot.mpd'); assert.equal(revision,'original'); assert.deepEqual(voxels,edited);
    return {model:{...model,file:'robot-edited.mpd',model_url:'/files/generated/robot-edited.mpd',parts:4},
      chat_id:'edit',support_voxels:1,voxels:repaired};
  });
  const createScene = (_host: HTMLDivElement, onPick: typeof pick) => {
    pick = onPick;
    return {update(rows: Cell[]) { updates.push(rows.map(row => [...row] as Cell)); },
      setTool() {}, fit() {}, dispose() {}};
  };
  try {
    await act(async () => root.render(<AppContext.Provider value={{
      openViewer(value: unknown) { opened.push(value); }, refreshChats() {},
    } as any}><SculptureEditor model={model} createScene={createScene} onClose={() => {closed=true;}} /></AppContext.Provider>));
    const dialog = document.querySelector('[aria-label="Sculpture editor"]')!;
    const button = (name: string) => [...dialog.querySelectorAll('button')].find(b => b.textContent === name)!;
    await act(async () => button('Add').click());
    await act(async () => pick(1,[1,0,0]));
    assert.deepEqual(updates.at(-1),edited);
    await act(async () => button('Save model').click());
    assert.deepEqual(updates.at(-1),repaired);
    assert.match(dialog.querySelector('[role="status"]')!.textContent!,/Added 1 support cells for connectivity/);
    assert.equal(button('Add').disabled,true);
    await act(async () => button('View saved model').click());
    assert.equal(opened[0].modelUrl,'/files/generated/robot-edited.mpd');
    assert.equal(closed,true);
  } finally {
    await act(async () => root.unmount()); element.remove();
  }
});

test('resize uses current saved revision, retries failures and keeps the resized model editable',async t=>{
  const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
  const initial:Cell[]=[[0,0,0,4],[7,0,1,4]],resized:Cell[]=[[0,0,0,4],[9,0,1,4]];
  const model:any={file:'import.mpd',description:'Imported model'};
  let pick:(index:number,normal:number[])=>void=()=>assert.fail('No scene');
  const updates:Cell[][]=[];let attempts=0,closed=0;
  let finish:(value:any)=>void=()=>assert.fail('Not resizing');
  const events:any[]=[];
  Object.assign(window,{posthog:{capture(event:string,properties:object){events.push({event,properties});}}});
  t.mock.method(api,'sculpture',async()=>({voxels:initial,revision:'original',resize_source:'mesh',palette:[]}));
  t.mock.method(api,'resizeSculpture',async(file:string,resolution:number,revision:string)=>{
    assert.equal(file,'import.mpd');assert.equal(resolution,10);assert.equal(revision,'original');attempts++;
    if(attempts===1)throw new Error('Choose a smaller size');
    return new Promise(resolve=>{finish=resolve;});
  });
  t.mock.method(api,'saveSculpture',async(file:string,rows:Cell[],revision:string)=>{
    assert.equal(file,'resized.mpd');assert.equal(revision,'resized-revision');assert.equal(rows.at(-1)![0],10);
    return {model:{file:'edited.mpd'},voxels:rows,support_voxels:0} as any;
  });
  const factory=(_host:HTMLElement,onPick:typeof pick)=>{pick=onPick;return{update(rows:Cell[]){updates.push(rows);},setTool(){},fit(){},dispose(){}};};
  try{
    await act(async()=>root.render(<AppContext.Provider value={{refreshChats(){},openViewer(){}} as any}><SculptureEditor model={model} createScene={factory} onClose={()=>closed++}/></AppContext.Provider>));
    const dialog=document.querySelector('[aria-label="Sculpture editor"]')!;
    const button=(label:string)=>[...dialog.querySelectorAll('button')].find(b=>b.textContent===label)!;
    const slider=dialog.querySelector('input[type="range"]') as HTMLInputElement;
    assert.equal(slider.value,'8');assert.match(dialog.textContent!,/original GLB/);
    await act(async()=>{
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value')!.set!.call(slider,'10');
      slider.dispatchEvent(new Event('input',{bubbles:true}));
    });
    await act(async()=>button('Resize model').click());
    assert.match(dialog.querySelector('[role="alert"]')!.textContent!,/smaller size/);
    await act(async()=>button('Resize model').click());
    assert.equal(slider.disabled,true);
    await act(async()=>document.dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape'})));
    assert.equal(closed,0);
    await act(async()=>finish({model:{file:'resized.mpd'},voxels:resized,revision:'resized-revision',resize_source:'mesh',brick_count:30,support_voxels:4}));
    assert.match(dialog.querySelector('[role="status"]')!.textContent!,/10 cells · 30 bricks/);
    assert.deepEqual(updates.at(-1),resized);
    assert.equal(button('Resize model').disabled,true);
    await act(async()=>button('Add').click());await act(async()=>pick(1,[1,0,0]));
    assert.match(dialog.textContent!,/Save or undo/);assert.equal(slider.disabled,true);
    await act(async()=>button('Save model').click());
    assert.equal(events.filter(e=>e.event==='sculpture_resize_started').length,2);
    assert(events.some(e=>e.event==='sculpture_resize_completed'&&e.properties.bricks===30));
    assert(events.every(e=>!('file' in e.properties)&&!('filename' in e.properties)));
  }finally{await act(async()=>root.unmount());host.remove();delete (window as any).posthog;}
});
