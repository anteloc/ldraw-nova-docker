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
