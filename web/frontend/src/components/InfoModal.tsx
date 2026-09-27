import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Markdown from "./Markdown";

/** A model's notes: its sibling .md (the prompt that made it, say), fetched when opened. */
export default function InfoModal({ title, url, onClose }: { title: string; url: string; onClose: () => void }) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    fetch(url)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(r.statusText || `HTTP ${r.status}`))))
      .then(
        (t) => alive && setText(t),
        (e) => alive && setError((e as Error).message),
      );
    return () => {
      alive = false;
    };
  }, [url]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal info-modal" role="dialog" aria-label={`About ${title}`} onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <strong className="ellipsis">{title}</strong>
          <button className="icon-button" aria-label="Close" onClick={onClose}>
            ✕
          </button>
        </header>
        <div className="info-body">
          {error ? (
            <p className="danger-text">Couldn't load the notes: {error}</p>
          ) : text === null ? (
            <p className="muted">
              <span className="spinner" aria-hidden /> Loading…
            </p>
          ) : (
            <Markdown>{text}</Markdown>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
