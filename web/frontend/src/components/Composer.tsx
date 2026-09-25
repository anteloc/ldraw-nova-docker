import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../context";

export default function Composer({
  llmId,
  onLlmChange,
  onSend,
  onStop,
  running,
  autoFocus,
  initialText = "",
}: {
  llmId: string | null;
  onLlmChange: (id: string) => void;
  onSend: (text: string) => Promise<void> | void;
  onStop?: () => void;
  running: boolean;
  autoFocus?: boolean;
  initialText?: string;
}) {
  const { llms } = useApp();
  const [text, setText] = useState(initialText);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => setText(initialText), [initialText]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 240) + "px";
  }, [text]);

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    const value = text.trim();
    if (!value || running || busy || llms.length === 0) return;
    setBusy(true);
    try {
      await onSend(value);
      setText("");
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      {llms.length === 0 && (
        <div className="composer-notice">
          No LLM configured yet. <Link to="/settings">Add a model in Settings</Link> to start chatting.
        </div>
      )}
      <textarea
        ref={ref}
        rows={1}
        value={text}
        autoFocus={autoFocus}
        placeholder="Describe a model to build, or ask about LDraw parts…"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="composer-bar">
        <select
          value={llmId ?? ""}
          onChange={(e) => onLlmChange(e.target.value)}
          disabled={llms.length === 0}
          aria-label="Model"
        >
          {llms.map((m) => (
            <option key={m.id} value={m.id}>
              {m.model_name}
            </option>
          ))}
        </select>
        <span className="muted small hint">Enter to send · Shift+Enter for a new line</span>
        {running ? (
          <button type="button" className="danger" onClick={onStop}>
            Stop
          </button>
        ) : (
          <button type="submit" className="primary" disabled={!text.trim() || busy || llms.length === 0}>
            Send
          </button>
        )}
      </div>
    </form>
  );
}
