import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, type ModelFile, type SculptureData } from "../api";
import { useApp } from "../context";
import { editCells, type Cell, type EditTool } from "../sculpture/cells";
import { SculptureScene } from "../sculpture/scene";

type EditorScene = Pick<SculptureScene, "update" | "setTool" | "fit" | "dispose">;
type SceneFactory = (host: HTMLDivElement, onEdit: (index: number, normal: number[]) => void) => EditorScene;
const defaultSceneFactory: SceneFactory = (host, onEdit) => new SculptureScene(host, onEdit);

export default function SculptureEditor({ model, onClose, createScene = defaultSceneFactory }: {
  model: ModelFile; onClose: () => void; createScene?: SceneFactory;
}) {
  const { openViewer, refreshChats } = useApp();
  const [data, setData] = useState<SculptureData | null>(null);
  const [cells, setCells] = useState<Cell[]>([]);
  const [tool, setTool] = useState<EditTool>("orbit");
  const [colour, setColour] = useState(4);
  const [history, setHistory] = useState<{ undo: Cell[][]; redo: Cell[][] }>({ undo: [], redo: [] });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState<{ model: ModelFile; support_voxels: number } | null>(null);
  const host = useRef<HTMLDivElement>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const scene = useRef<EditorScene | null>(null);
  const latest = useRef({ cells, tool, colour, busy, saved }); latest.current = { cells, tool, colour, busy, saved };
  const dirty = history.undo.length > 0;
  const close = () => { if (!busy && (!dirty || saved || confirm("Discard your unsaved sculpture edits?"))) onClose(); };
  const closeRef = useRef(close); closeRef.current = close;

  useEffect(() => {
    let alive = true;
    api.sculpture(model.file).then(value => {
      if (alive) { setData(value); setCells(value.voxels); setColour(value.voxels[0][3]); }
    }, e => { if (alive) setError((e as Error).message); });
    return () => { alive = false; };
  }, [model.file]);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.current?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); closeRef.current(); }
      if (e.key === "Tab") {
        const items = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), select:not(:disabled), a[href]') || []);
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { e.preventDefault(); last?.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("keydown", key); document.body.style.overflow = previousOverflow; previous?.focus(); };
  }, []);

  useEffect(() => {
    if (!data || !host.current) return;
    try {
      scene.current = createScene(host.current, (index, normal) => {
        const current = latest.current;
        if (current.busy || current.saved) return;
        const next = editCells(current.cells, index, current.tool, current.colour, normal);
        if (next !== current.cells) {
          setHistory(h => ({ undo: [...h.undo.slice(-49), current.cells], redo: [] }));
          setCells(next); setError("");
        }
      });
      scene.current.update(data.voxels, data.palette);
    } catch { setError("The 3D editor needs WebGL. Try a browser with hardware acceleration enabled."); }
    return () => { scene.current?.dispose(); scene.current = null; };
  }, [data, createScene]);
  useEffect(() => { scene.current?.update(cells, data?.palette || []); }, [cells, data]);
  useEffect(() => { scene.current?.setTool(busy || saved ? "orbit" : tool); }, [tool, busy, saved]);

  function travel(direction: "undo" | "redo") {
    const stack = history[direction]; if (!stack.length) return;
    const other = direction === "undo" ? "redo" : "undo";
    setCells(stack[stack.length - 1]);
    setHistory({ ...history, [direction]: stack.slice(0, -1), [other]: [...history[other], cells] }); setError("");
  }
  async function save() {
    if (!data) return;
    setBusy(true); setError("");
    try {
      const result = await api.saveSculpture(model.file, cells, data.revision);
      setCells(result.voxels);
      setSaved(result); setHistory({ undo: [], redo: [] }); refreshChats();
      window.dispatchEvent(new Event("models-changed"));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const palette = data?.palette || [];
  const used = new Set(cells.map(c => c[3]));
  const choices = palette.filter(c => used.has(c.code) || [0, 1, 2, 4, 6, 7, 14, 15].includes(c.code));
  const enabled = !!data && !busy && !saved;

  return createPortal(<div className="modal-backdrop" onClick={close}>
    <div ref={dialog} className="modal sculpture-editor" role="dialog" aria-modal="true" aria-label="Sculpture editor" tabIndex={-1} onClick={e => e.stopPropagation()}>
      <header className="modal-head"><div><strong>Sculpture editor</strong><div className="muted small ellipsis">{model.description || model.file}</div></div>
        <button className="icon-button" aria-label="Close sculpture editor" disabled={busy} onClick={close}>✕</button></header>
      <div className="sculpture-editor-tools">
        <div className="button-group" role="group" aria-label="Sculpture tools">
          {([['orbit', 'Rotate'], ['add', 'Add'], ['paint', 'Paint'], ['erase', 'Erase']] as const).map(([value, label]) =>
            <button key={value} aria-pressed={tool === value} disabled={!enabled} onClick={() => setTool(value)}>{label}</button>)}
        </div>
        <div className="button-group" role="group" aria-label="Edit history"><button disabled={!enabled || !history.undo.length} onClick={() => travel('undo')}>Undo</button><button disabled={!enabled || !history.redo.length} onClick={() => travel('redo')}>Redo</button></div>
        <button disabled={!data} onClick={() => scene.current?.fit()}>Fit view</button>
      </div>
      <div className="sculpture-editor-colours" role="group" aria-label="Sculpture colours">
        {choices.map(c => <button key={c.code} className="sculpture-swatch" style={{ backgroundColor: c.hex }} aria-label={c.name} title={c.name} aria-pressed={colour === c.code} disabled={!enabled} onClick={() => setColour(c.code)} />)}
        <select aria-label="All brick colours" value={colour} disabled={!enabled} onChange={e => setColour(Number(e.target.value))}>{palette.map(c => <option key={c.code} value={c.code}>{c.name}</option>)}</select>
      </div>
      <div ref={host} className="sculpture-canvas">{!data && !error && <span className="sculpture-loading">Loading sculpture…</span>}</div>
      <div className="sculpture-editor-footer">
        {error && <p className="danger-text" role="alert">{error}</p>}
        {saved ? <><p role="status">Saved a new model version.{saved.support_voxels > 0 ? ` Added ${saved.support_voxels} support cells for connectivity.` : ''} Your original is in My Models.</p><button className="primary" onClick={() => { if (saved.model.model_url) openViewer({ modelUrl: saved.model.model_url, title: saved.model.file, parts: saved.model.parts, mode: 'viewer' }); onClose(); }}>View saved model</button></> : <>
          <p className="muted small">{tool === 'orbit' ? 'Drag to rotate. Scroll or pinch to zoom.' : `Click or tap a cell to ${tool === 'add' ? 'add to its face' : tool === 'paint' ? 'paint it' : 'erase it'}. Right-drag to rotate; use two fingers on touch.`} {cells.length.toLocaleString()} cells.</p>
          <div className="sculpture-save-row"><span className="muted small">Saving repairs connections and rebuilds instructions.</span><button className="primary" disabled={!enabled || !dirty} onClick={save}>{busy ? <><span className="spinner" aria-hidden /> Rebuilding model…</> : 'Save model'}</button></div>
        </>}
      </div>
    </div>
  </div>, document.body);
}
