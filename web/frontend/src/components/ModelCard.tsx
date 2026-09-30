import { useState } from "react";
import { Link } from "react-router-dom";
import { downloadGlb, downloadUrl, partsLabel, timeAgo, XR_TITLE, xrUrl, type ModelFile, type ViewerMode } from "../api";
import { useApp } from "../context";
import InfoModal from "./InfoModal";

type Props = {
  model: ModelFile & { warnings?: string[]; created_at?: number };
  showChats?: boolean;
  onDelete?: () => Promise<void>;
};

function DownloadIcon() {
  return (
    <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
      <path d="M8 2v8m-3-3 3 3 3-3M3 11v3h10v-3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function ModelCard({ model, showChats = false, onDelete }: Props) {
  const { openViewer } = useApp();
  const open = (mode: ViewerMode = "viewer") =>
    model.model_url &&
    openViewer({ modelUrl: model.model_url, title: model.description || model.file, parts: model.parts, mode });
  const warnings = model.warnings ?? [];
  const extension = "." + (model.file.split(".").pop() ?? "mpd").toLowerCase();
  const bomBusy = model.bom_status === "queued" || model.bom_status === "rendering";
  const [glb, setGlb] = useState<{ busy: boolean; error?: string }>({ busy: false });
  const [info, setInfo] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  async function remove() {
    if (!onDelete || !confirm(`Delete “${model.file}” and its preview, parts list and notes from My Models? This cannot be undone. Original chat work files are kept.`)) return;
    setDeleting(true); setDeleteError("");
    try { await onDelete(); }
    catch (e) { setDeleteError((e as Error).message); }
    finally { setDeleting(false); }
  }

  async function saveGlb() {
    if (!model.model_url) return;
    setGlb({ busy: true });
    try {
      await downloadGlb(model.model_url, model.file);
      setGlb({ busy: false });
    } catch (e) {
      setGlb({ busy: false, error: (e as Error).message });
    }
  }

  let thumb;
  if (model.image_url) {
    thumb = <img src={model.image_url} alt={model.description || model.file} loading="lazy" />;
  } else if (model.status === "queued" || model.status === "rendering") {
    thumb = (
      <span className="thumb-missing">
        <span className="spinner" aria-hidden /> {model.status === "rendering" ? "Rendering snapshot…" : "Waiting to render…"}
      </span>
    );
  } else if (model.status === "failed") {
    thumb = <span className="thumb-missing" title={model.error ?? ""}>Snapshot failed — open in 3D</span>;
  } else {
    thumb = <span className="thumb-missing">This model was deleted from My Models</span>;
  }

  return (
    <div className="model-card">
      {onDelete && !model.gallery && <button type="button" className="model-delete" aria-label={`Delete ${model.file}`} title="Delete model" disabled={deleting} onClick={remove}>
        {deleting ? <span className="spinner" aria-hidden="true" /> : "×"}
      </button>}
      <button className="model-thumb" onClick={() => open()} disabled={!model.model_url} title="Open in the 3D viewer">
        {thumb}
        {model.model_url && <span className="thumb-hint">View in 3D</span>}
      </button>
      <div className="model-meta">
        {deleteError && <p className="warn-text small" role="alert">{deleteError}</p>}
        <div className="model-title">
          <span className="model-file">
            <strong className="ellipsis" title={model.file}>{model.file}</strong>
            {model.parts != null ? (
              <span className="muted">, {partsLabel(model.parts)}</span>
            ) : bomBusy ? (
              <span className="muted">, counting parts…</span>
            ) : null}
          </span>
          {warnings.length > 0 && (
            <span className="badge warn" title={warnings.join("\n")}>
              {warnings.length} warning{warnings.length > 1 ? "s" : ""}
            </span>
          )}
        </div>
        {model.info_heading && <p className="model-info-heading"><strong>{model.info_heading}</strong></p>}
        {model.description && <p className="model-description">{model.description}</p>}
        <div className="muted small ellipsis">
          {model.gallery ? "From the gallery" : timeAgo(model.created_at ?? model.mtime)}
          {showChats && model.chats && model.chats.length > 0 && (
            <>
              {" · from "}
              {model.chats.map((c, i) => (
                <span key={c.id}>
                  {i > 0 && ", "}
                  <Link to={`/chat/${c.id}`}>{c.title}</Link>
                </span>
              ))}
            </>
          )}
        </div>
        <div className="model-actions">
          {model.info_url && (
            <button className="model-info-action" onClick={() => setInfo(true)} title="About this model, from its author (e.g. the prompt that made it)">
              <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
                <circle cx="8" cy="8" r="6" /><path d="M8 7v4M8 4.5v1" strokeLinecap="round" />
              </svg>
              Info
            </button>
          )}
          <span className="model-viewer-actions" role="group" aria-label="View model">
            <button onClick={() => open()} disabled={!model.model_url}>
              3D View
            </button>
            <button onClick={() => open("player")} disabled={!model.model_url} title="Watch the model being built, step by step">
              3D Player
            </button>
            {model.model_url && (
              <a className="button" href={xrUrl(model.model_url, model.parts)} title={XR_TITLE}>
                VR
              </a>
            )}
          </span>
          <span className="button-group model-download-actions" role="group" aria-label="Download">
            {model.model_url && (
              <a className="button" href={downloadUrl(model.model_url)} title={`Download ${model.file}`}>
                <DownloadIcon /> {extension}
              </a>
            )}
            {model.model_url && (
              <button
                onClick={saveGlb}
                disabled={glb.busy}
                title={
                  glb.busy
                    ? "Converting with mpd2glb… big models can take a minute"
                    : glb.error
                      ? `Conversion failed: ${glb.error}`
                      : "Download as glTF binary (.glb), converted with mpd2glb"
                }
                aria-label={glb.busy ? "Converting to .glb" : undefined}
                className={glb.error ? "danger-text" : undefined}
              >
                {glb.busy ? <span className="spinner" aria-hidden /> : <DownloadIcon />}
                .glb
              </button>
            )}
            {model.bom_url ? (
              <a className="button" href={downloadUrl(model.bom_url)} title="Download the bill of materials (CSV)">
                <DownloadIcon /> BOM
              </a>
            ) : model.model_url ? (
              <button disabled title={bomBusy ? "Generating the bill of materials…" : (model.bom_error ?? "No bill of materials")}>
                <DownloadIcon /> BOM
              </button>
            ) : null}
          </span>
        </div>
      </div>
      {info && model.info_url && (
        <InfoModal title={model.description || model.file} url={model.info_url} onClose={() => setInfo(false)} />
      )}
    </div>
  );
}
