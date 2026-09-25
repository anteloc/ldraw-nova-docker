import { useEffect, useState } from "react";
import { api, type Artifact } from "../api";
import ModelCard from "../components/ModelCard";

export default function Gallery() {
  const [artifacts, setArtifacts] = useState<Artifact[] | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.artifacts().then((r) => setArtifacts(r.artifacts));
  }, []);

  const q = query.trim().toLowerCase();
  const shown = (artifacts ?? []).filter(
    (a) => !q || a.name.toLowerCase().includes(q) || (a.chat_title ?? "").toLowerCase().includes(q),
  );

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Models</h1>
          <p className="muted">Every model the agents generated, newest first. Files live in data/generated/.</p>
        </div>
        <input type="search" placeholder="Filter by name or chat" value={query} onChange={(e) => setQuery(e.target.value)} />
      </header>
      {artifacts === null && <p className="muted">Loading…</p>}
      {artifacts?.length === 0 && <p className="muted">No models yet — start a chat and ask for one.</p>}
      <div className="card-grid">
        {shown.map((a) => (
          <ModelCard key={a.id} artifact={a} showChat />
        ))}
      </div>
    </div>
  );
}
