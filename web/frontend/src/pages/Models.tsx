import { useEffect, useState } from "react";
import { api, type ModelFile } from "../api";
import ModelCard from "../components/ModelCard";

// Opening the page scans data/generated; the backend queues snapshots for models
// that have none, and we poll until they're all rendered.
const POLL_MS = 1500;

export default function Models() {
  const [models, setModels] = useState<ModelFile[] | null>(null);
  const [pending, setPending] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const r = await api.models();
        if (!alive) return;
        setModels(r.models);
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
  }, []);

  const q = query.trim().toLowerCase();
  const shown = (models ?? []).filter(
    (m) =>
      !q ||
      m.file.toLowerCase().includes(q) ||
      m.description.toLowerCase().includes(q) ||
      (m.chats ?? []).some((c) => c.title.toLowerCase().includes(q)),
  );

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Models</h1>
          <p className="muted">
            Everything in <code>data/generated</code> — from chats or added by hand. Each model's snapshot (
            <code>.png</code>) and bill of materials (<code>.csv</code>) sit next to it; missing ones are made with
            LeoCAD.
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
          <input type="search" placeholder="Filter by name, description or chat" value={query} onChange={(e) => setQuery(e.target.value)} />
          {models && models.length > 0 && (
            <a className="button" href="/api/models/zip">
              Download all (.zip)
            </a>
          )}
        </div>
      </header>
      {error && <div className="banner error">{error}</div>}
      {models === null && !error && <p className="muted">Scanning data/generated…</p>}
      {models?.length === 0 && (
        <p className="muted">No models yet. Ask for one in a chat, or drop .mpd/.ldr/.dat files into data/generated.</p>
      )}
      <div className="card-grid">
        {shown.map((m) => (
          <ModelCard key={m.file} model={m} showChats />
        ))}
      </div>
    </div>
  );
}
