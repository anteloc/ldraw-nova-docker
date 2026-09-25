import { Link } from "react-router-dom";
import { fileUrl, timeAgo, type Artifact } from "../api";
import { useApp } from "../context";

export default function ModelCard({ artifact, showChat = false }: { artifact: Artifact; showChat?: boolean }) {
  const { openViewer } = useApp();
  const open = () => openViewer({ modelUrl: fileUrl(artifact.model_path), title: artifact.name });
  const file = artifact.model_path.split("/").pop();

  return (
    <div className="model-card">
      <button className="model-thumb" onClick={open} title="Open in the 3D viewer">
        {artifact.image_path ? (
          <img src={fileUrl(artifact.image_path)} alt={artifact.name} loading="lazy" />
        ) : (
          <span className="thumb-missing">Render failed — open in 3D</span>
        )}
        <span className="thumb-hint">View in 3D</span>
      </button>
      <div className="model-meta">
        <div className="model-title">
          <strong className="ellipsis">{artifact.name}</strong>
          {artifact.warnings.length > 0 && (
            <span className="badge warn" title={artifact.warnings.join("\n")}>
              {artifact.warnings.length} warning{artifact.warnings.length > 1 ? "s" : ""}
            </span>
          )}
        </div>
        <div className="muted small ellipsis">
          {file} · {timeAgo(artifact.created_at)}
          {showChat && artifact.chat_title && (
            <>
              {" · "}
              <Link to={`/chat/${artifact.chat_id}`}>{artifact.chat_title}</Link>
            </>
          )}
        </div>
        <div className="model-actions">
          <button onClick={open}>3D view</button>
          <a className="button" href={fileUrl(artifact.model_path, true)}>
            Download .mpd
          </a>
          {artifact.image_path && (
            <a className="button" href={fileUrl(artifact.image_path, true)}>
              .png
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
