import { useEffect, useState } from "react";
import { viewerUrl, type ViewerMode } from "../api";
import type { ViewerTarget } from "../context";

const MODES: { mode: ViewerMode; label: string; title: string }[] = [
  { mode: "viewer", label: "3D view", title: "Inspect the model (three.js viewer)" },
  { mode: "player", label: "3D player", title: "Watch it being built, step by step" },
];

// The viewer and the player are separate pages in an iframe: the viewer's
// three.js/ldbi scripts are classic globals (THREE, LDR) that shouldn't mix
// with the React app, and the player is a WebAssembly module with its own loop.
export default function ViewerModal({ target, onClose }: { target: ViewerTarget; onClose: () => void }) {
  const [mode, setMode] = useState<ViewerMode>(target.mode ?? "viewer");
  useEffect(() => setMode(target.mode ?? "viewer"), [target]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onClose]);

  const url = viewerUrl(target.modelUrl, target.parts, mode);
  const label = `${mode === "player" ? "3D player" : "3D view"} of ${target.title}`;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-label={label} onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <strong className="ellipsis">{target.title}</strong>
          <span className="segmented" role="group" aria-label="Show in">
            {MODES.map((m) => (
              <button key={m.mode} aria-pressed={mode === m.mode} title={m.title} onClick={() => setMode(m.mode)}>
                {m.label}
              </button>
            ))}
          </span>
          <a href={url} target="_blank" rel="noreferrer">
            Open in new tab
          </a>
          <button className="icon-button" aria-label="Close" onClick={onClose}>
            ✕
          </button>
        </header>
        {/* key: a fresh page per mode, so the iframe's history doesn't pile up */}
        <iframe key={url} src={url} title={label} allow="fullscreen" />
      </div>
    </div>
  );
}
