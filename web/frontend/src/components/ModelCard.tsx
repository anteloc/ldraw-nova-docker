import { Link } from "react-router-dom";
import { downloadUrl, partsLabel, timeAgo, type ModelFile } from "../api";
import { useApp } from "../context";

type Props = {
  model: ModelFile & { warnings?: string[]; created_at?: number };
  showChats?: boolean;
};

export default function ModelCard({ model, showChats = false }: Props) {
  const { openViewer } = useApp();
  const open = () =>
    model.model_url && openViewer({ modelUrl: model.model_url, title: model.description || model.file, parts: model.parts });
  const warnings = model.warnings ?? [];
  const extension = "." + (model.file.split(".").pop() ?? "mpd").toLowerCase();
  const bomBusy = model.bom_status === "queued" || model.bom_status === "rendering";

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
    thumb = <span className="thumb-missing">No longer in data/generated</span>;
  }

  return (
    <div className="model-card">
      <button className="model-thumb" onClick={open} disabled={!model.model_url} title="Open in the 3D viewer">
        {thumb}
        {model.model_url && <span className="thumb-hint">View in 3D</span>}
      </button>
      <div className="model-meta">
        <div className="model-title">
          <span className="ellipsis">
            <strong>{model.file}</strong>
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
        {model.description && <p className="model-description">{model.description}</p>}
        <div className="muted small ellipsis">
          {timeAgo(model.created_at ?? model.mtime)}
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
          <button onClick={open} disabled={!model.model_url}>
            3D view
          </button>
          {model.model_url && (
            <a className="button" href={downloadUrl(model.model_url)} title={`Download ${model.file}`}>
              {extension}
            </a>
          )}
          {model.bom_url ? (
            <a className="button" href={downloadUrl(model.bom_url)} title="Download the bill of materials (CSV)">
              BOM
            </a>
          ) : model.model_url ? (
            <button disabled title={bomBusy ? "Generating the bill of materials…" : (model.bom_error ?? "No bill of materials")}>
              BOM
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
