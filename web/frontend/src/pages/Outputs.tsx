import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, formatSize, timeAgo, type OutputListing } from "../api";
import { useApp } from "../context";

export default function Outputs() {
  const dir = useParams()["*"] ?? "";
  const { openViewer } = useApp();
  const [listing, setListing] = useState<OutputListing | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setListing(null);
    setError(null);
    api.outputs(dir).then(setListing).catch((e) => setError(e.message));
  }, [dir]);

  const crumbs = dir ? dir.split("/") : [];

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Outputs</h1>
          <nav className="crumbs" aria-label="Folder">
            <Link to="/outputs">data/output</Link>
            {crumbs.map((c, i) => (
              <span key={i}>
                {" / "}
                <Link to={`/outputs/${crumbs.slice(0, i + 1).join("/")}`}>{c}</Link>
              </span>
            ))}
          </nav>
        </div>
        <a className="button" href={`/api/outputs/zip?dir=${encodeURIComponent(dir)}`}>
          Download folder (.zip)
        </a>
      </header>

      {error && <div className="banner error">{error}</div>}
      {!listing && !error && <p className="muted">Loading…</p>}
      {listing && listing.dirs.length === 0 && listing.files.length === 0 && (
        <p className="muted">Empty. Renders from chats, leocad_render.py and example.py land here.</p>
      )}

      {listing && listing.dirs.length > 0 && (
        <div className="folder-list">
          {listing.dirs.map((d) => (
            <Link key={d.path} className="folder" to={`/outputs/${d.path}`}>
              <span aria-hidden>📁</span> {d.name}
            </Link>
          ))}
        </div>
      )}

      <div className="card-grid">
        {listing?.files.map((f) => (
          <div key={f.path} className="model-card">
            {f.is_image ? (
              <a className="model-thumb" href={f.url} target="_blank" rel="noreferrer">
                <img src={f.url} alt={f.name} loading="lazy" />
              </a>
            ) : (
              <div className="model-thumb file-thumb">{f.name.split(".").pop()}</div>
            )}
            <div className="model-meta">
              <strong className="ellipsis">{f.name}</strong>
              <div className="muted small">
                {formatSize(f.size)} · {timeAgo(f.mtime)}
                {f.source && <> · from {f.source.name}</>}
              </div>
              <div className="model-actions">
                <a className="button" href={`${f.url}?download=1`}>
                  Download
                </a>
                {f.source && (
                  <>
                    <button onClick={() => openViewer({ modelUrl: f.source!.url, title: f.source!.name })}>3D view</button>
                    <a className="button" href={`${f.source.url}?download=1`}>
                      Model
                    </a>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
