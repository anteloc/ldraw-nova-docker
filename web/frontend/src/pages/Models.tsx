import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { api, type ModelFile } from "../api";
import ModelCard from "../components/ModelCard";
import GlbImport from "../components/GlbImport";

const SculptureEditor = lazy(() => import("../components/SculptureEditor"));

// Opening the page scans data/generated; the backend queues snapshots for models
// that have none, and we poll until they're all rendered.
const POLL_MS = 1500;

export default function Models({ collection }: { collection: "models" | "gallery" }) {
  const isGallery = collection === "gallery";
  const [models, setModels] = useState<ModelFile[] | null>(null);
  const [revision, setRevision] = useState(0);
  const [pending, setPending] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [importing, setImporting] = useState(false);
  const [editing, setEditing] = useState<ModelFile | null>(null);
  const deleted = useRef(new Set<string>());

  useEffect(() => {
    const changed = () => setRevision(v => v + 1);
    window.addEventListener("models-changed", changed);
    return () => window.removeEventListener("models-changed", changed);
  }, []);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const r = await api.models(collection);
        if (!alive) return;
        setModels(r.models.filter(model => !deleted.current.has(model.file)));
        setPending(r.pending);
        setError(null);
        if (r.pending > 0) timer = setTimeout(load, POLL_MS);
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
    };
    load();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [collection, revision]);

  const q = query.trim().toLowerCase();
  const shown = (models ?? []).filter(
    (m) =>
      !q ||
      m.file.toLowerCase().includes(q) ||
      (m.info_heading ?? "").toLowerCase().includes(q) ||
      m.description.toLowerCase().includes(q) ||
      (m.chats ?? []).some((c) => c.title.toLowerCase().includes(q)),
  );

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>{isGallery ? "Gallery" : "My Models"}</h1>
          <p className="muted">
            {isGallery
              ? "Explore the models included with LDraw Nova. Inspect them in 3D, watch them build, or download them."
              : "Your generated models and models you’ve added. Open a model to explore it in 3D."}
            {pending > 0 && (
              <>
                {" "}
                <span className="warn-text">
                  <span className="spinner" aria-hidden /> Processing {pending} model{pending > 1 ? "s" : ""}…
                </span>
              </>
            )}
          </p>
        </div>
        <div className="head-actions">
          {!isGallery && <button className="primary" onClick={() => setImporting(true)}>Import GLB</button>}
          <input type="search" aria-label="Filter models" placeholder={isGallery ? "Filter by name or description" : "Filter by name, description or chat"} value={query} onChange={(e) => setQuery(e.target.value)} />
          {models && models.length > 0 && (
            <a className="button" href={`/api/${collection}/zip`}>
              Download all (.zip)
            </a>
          )}
        </div>
      </header>
      {error && <div className="banner error">{error}</div>}
      {models === null && !error && <p className="muted">Loading models…</p>}
      {models?.length === 0 && (
        <p className="muted">{isGallery
          ? "No gallery models yet. Add models to models-gallery to include them here."
          : "No models yet. Import a GLB to make a LEGO sculpture, or ask for a model in a chat."}</p>
      )}
      {models && models.length > 0 && shown.length === 0 && <p className="muted">No models match your search.</p>}
      <div className="card-grid">
        {shown.map((m) => (
          <ModelCard key={m.file} model={m} showChats={!isGallery} onDelete={isGallery ? undefined : async () => {
            await api.deleteModel(m.file);
            deleted.current.add(m.file);
            setModels(current => current?.filter(model => model.file !== m.file) ?? null);
          }} />
        ))}
      </div>
      {importing && <GlbImport onClose={() => setImporting(false)} onEdit={model => { setImporting(false); setEditing(model); }} />}
      {editing && <Suspense fallback={null}><SculptureEditor model={editing} onClose={() => setEditing(null)} /></Suspense>}
    </div>
  );
}
