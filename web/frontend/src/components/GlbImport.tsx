import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, type ModelFile } from "../api";
import { useApp } from "../context";

// Follow the host's PostHog integration when present; importing a local model
// never installs an analytics client or sends file names or mesh contents.
export function trackGlbImport(event: string, properties: Record<string, number | string> = {}) {
  (window as Window & { posthog?: { capture: (event: string, properties: object) => void } })
    .posthog?.capture(event, properties);
}

export function validateGlbFile(file: File): string {
  if (!file.name.toLowerCase().endsWith(".glb")) return "Choose a binary glTF (.glb) file.";
  if (file.size < 20) return "This GLB file is empty or incomplete.";
  if (file.size > 16 * 1024 * 1024) return "Keep the GLB within 16 MB.";
  return "";
}

export default function GlbImport({ onClose, onEdit }: { onClose: () => void; onEdit: (model: ModelFile) => void }) {
  const { openViewer, refreshChats } = useApp();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [resolution, setResolution] = useState<number | "auto">("auto");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.importGlb>> | null>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const closeRef = useRef(() => {});
  closeRef.current = () => { if (!busy) { trackGlbImport("glb_import_closed"); onClose(); } };
  useEffect(() => {
    trackGlbImport("glb_import_opened");
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.current?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); closeRef.current(); }
      if (event.key === "Tab") {
        const items = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled)') || []);
        const first = items[0], last = items.at(-1);
        if (!first) { event.preventDefault(); return; }
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("keydown", key); document.body.style.overflow = overflow; previous?.focus(); };
  }, []);

  async function convert(event: React.FormEvent) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true); setError("");
    trackGlbImport("glb_import_started", { resolution, bytes: file.size });
    try {
      const saved = await api.importGlb(file, resolution, title.trim());
      setResult(saved); refreshChats();
      window.dispatchEvent(new Event("models-changed"));
      trackGlbImport("glb_import_completed", { resolution, surface_voxels: saved.import.surface_voxels, support_voxels: saved.support_voxels });
    } catch (failure) {
      setError((failure as Error).message);
      trackGlbImport("glb_import_failed", { resolution });
    } finally { setBusy(false); }
  }

  return createPortal(<div className="modal-backdrop" onClick={() => closeRef.current()}>
    <div className="modal glb-import" role="dialog" aria-modal="true" aria-label="GLB to LEGO" tabIndex={-1} ref={dialog} onClick={event => event.stopPropagation()}>
      <header className="modal-head"><strong>GLB to LEGO</strong><button className="icon-button" aria-label="Close import" disabled={busy} onClick={() => closeRef.current()}>×</button></header>
      <div className="glb-import-body">
        {result ? <>
          <div className="glb-import-ready" role="status"><span className="glb-import-symbol" aria-hidden>✓</span><h2>Your sculpture is ready</h2>
            <p>{result.import.brick_count.toLocaleString()} bricks · {result.import.palette_colors} colors · {result.import.surface_voxels.toLocaleString()} surface cells</p>
            <p className="muted">Voxel world: {result.import.dimensions.join(" × ")} cells{result.import.target_bricks ? ` · Target: ~${result.import.target_bricks.toLocaleString()} bricks` : ""}.</p>
            {result.import.target_reached === false && <p className="muted">Used the closest successfully connected size within the conversion limits. Try a simpler mesh to get closer to the target.</p>}
            <p className="muted">Added {result.support_voxels.toLocaleString()} support cells. Saved to My Models with connected build steps.</p>
          </div>
          <div className="glb-import-actions"><button className="primary" onClick={() => { trackGlbImport("glb_import_editor_opened"); onEdit(result.model); }}>Edit voxels</button>
            <button onClick={() => { trackGlbImport("glb_import_viewed"); openViewer({ modelUrl: result.model.model_url!, title: result.model.description, parts: result.model.parts }); onClose(); }}>View LEGO model</button></div>
        </> : <form onSubmit={convert}>
          <p className="glb-import-intro">Turn a colored 3D mesh into a LEGO sculpture.</p>
          <p className="muted">Colors become LEGO colors. The sculpture pipeline fills the shell, packs bricks and adds support cells where needed to connect the parts.</p>
          <label className="glb-file-field">3D model <span className="muted small">.glb · up to 16 MB · embedded PNG/JPEG textures</span>
            <input type="file" accept=".glb,model/gltf-binary" disabled={busy} onChange={event => {
              const selected = event.target.files?.[0]; if (!selected) return;
              const issue = validateGlbFile(selected); setError(issue); setFile(issue ? null : selected);
              if (!issue) { setTitle(selected.name.replace(/\.glb$/i, "").slice(0, 120)); trackGlbImport("glb_import_file_selected", { bytes: selected.size }); }
            }} /></label>
          <label>Model name<input value={title} maxLength={120} required disabled={busy} placeholder="My sculpture" onChange={event => setTitle(event.target.value)} /></label>
          <label>Detail level<select value={resolution} disabled={busy} onChange={event => { const value = event.target.value === "auto" ? "auto" : Number(event.target.value); setResolution(value); trackGlbImport("glb_import_resolution_changed", { resolution: value }); }}>
            <option value="auto">Auto · about 3,000 bricks</option><option value={16}>Low · 16 studs</option><option value={24}>Balanced · 24 studs</option><option value={32}>Detailed · 32 studs</option><option value={48}>Fine · 48 studs</option></select>
            <span className="muted small">Auto chooses the world dimensions from the packed brick count. Manual sizes set the longest grid dimension.</span></label>
          {error && <p className="banner error" role="alert">{error}</p>}
          {busy && <div className="glb-import-progress" role="status"><span className="spinner" aria-hidden /><div><strong>Building your sculpture…</strong><p className="muted small">{resolution === "auto" ? "Choosing a size for about 3,000 bricks, " : "Voxelizing colors, "}repairing connections and rendering. This can take several minutes. Keep this window open.</p></div></div>}
          <div className="glb-import-actions"><button type="submit" className="primary" disabled={!file || !title.trim() || busy}>{busy ? "Converting…" : "Convert to LEGO"}</button><button type="button" disabled={busy} onClick={() => closeRef.current()}>Cancel</button></div>
        </form>}
      </div>
    </div>
  </div>, document.body);
}
