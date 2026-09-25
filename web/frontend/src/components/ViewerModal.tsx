import { useEffect } from "react";
import { viewerUrl } from "../api";
import type { ViewerTarget } from "../context";

// The viewer is a separate page in an iframe: its three.js/ldbi scripts are
// classic globals (THREE, LDR) that shouldn't mix with the React app.
export default function ViewerModal({ target, onClose }: { target: ViewerTarget; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onClose]);

  const url = viewerUrl(target.modelUrl);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-label={`3D view of ${target.title}`} onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <strong className="ellipsis">{target.title}</strong>
          <a href={url} target="_blank" rel="noreferrer">
            Open in new tab
          </a>
          <button className="icon-button" aria-label="Close" onClick={onClose}>
            ✕
          </button>
        </header>
        <iframe src={url} title={`3D view of ${target.title}`} />
      </div>
    </div>
  );
}
