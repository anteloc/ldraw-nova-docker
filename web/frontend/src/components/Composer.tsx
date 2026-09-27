import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../context";
import type { TurnOptions } from "../api";

export default function Composer({
  llmId,
  onLlmChange,
  onSend,
  onStop,
  running,
  autoFocus,
  initialText = "",
  initialOptions,
}: {
  llmId: string | null;
  onLlmChange: (id: string) => void;
  onSend: (text: string, options: TurnOptions, images: string[]) => Promise<void> | void;
  onStop?: () => void;
  running: boolean;
  autoFocus?: boolean;
  initialText?: string;
  initialOptions?: TurnOptions;
}) {
  const { llms } = useApp();
  const [text, setText] = useState(initialText);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);
  const [options, setOptions] = useState<TurnOptions>(initialOptions ?? { mode: "agent", permissions: "ask" });
  const [images, setImages] = useState<{ name: string; url: string }[]>([]);
  const [error, setError] = useState("");
  const model = llms.find(m => m.id === llmId);
  const profile = model?.profile;
  useEffect(() => {
    setOptions(o => ({ ...o,
      effort: o.effort && profile?.efforts.includes(o.effort) ? o.effort : null,
      context_tokens: o.context_tokens && profile?.context_budgets.includes(o.context_tokens) ? o.context_tokens : null,
    }));
  }, [llmId, profile]);

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
      setError("");
      if (images.length && model?.resolved_capabilities.vision !== true) throw new Error("Choose a model that supports images or remove the attachments.");
      await onSend(value, options, images.map(i => i.url));
      setText("");
      setImages([]);
    } catch (e) {
      setError((e as Error).message);
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
      {images.length > 0 && <div className="attachments">{images.map((img, index) => <div key={index}>
        <img src={img.url} alt={img.name} /><button type="button" aria-label={`Remove ${img.name}`} onClick={() => setImages(images.filter((_, i) => i !== index))}>✕</button>
      </div>)}</div>}
      {error && <div className="banner error" role="alert">{error}</div>}
      <div className="turn-options">
        <label><span>Mode</span><select aria-label="Mode" disabled={running} value={options.mode} onChange={e => setOptions({ ...options, mode: e.target.value as TurnOptions["mode"] })}>
          <option value="agent">Agent</option><option value="plan">Plan (read only)</option><option value="chat">Chat</option>
        </select></label>
        {options.mode === "agent" && <label><span>Permissions</span><select aria-label="Permissions" disabled={running} value={options.permissions} onChange={e => setOptions({ ...options, permissions: e.target.value as TurnOptions["permissions"] })}>
          <option value="ask">Ask before changes</option><option value="full">Full access (container)</option><option value="read_only">Read only</option>
        </select></label>}
        {!!profile?.efforts.length && <label><span>Effort</span><select aria-label="Effort" disabled={running} value={options.effort ?? ""} onChange={e => setOptions({ ...options, effort: e.target.value || null })}>
          <option value="">Provider default</option>{profile.efforts.map(e => <option key={e}>{e}</option>)}
        </select></label>}
        {!!profile?.context_budgets.length && <label><span>Context budget</span><select aria-label="Context budget" disabled={running} value={options.context_tokens ?? ""} onChange={e => setOptions({ ...options, context_tokens: e.target.value ? Number(e.target.value) : null })}>
          <option value="">Auto ({profile.context_window?.toLocaleString()})</option>{profile.context_budgets.map(n => <option value={n} key={n}>{n.toLocaleString()} tokens</option>)}
        </select></label>}
        {model?.resolved_capabilities.vision === true && <label className="image-upload"><span>Attach images</span><input aria-label="Attach images" type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={running || busy} onChange={async e => {
          const files = Array.from(e.target.files ?? []); e.target.value = "";
          setError("");
          if (files.length + images.length > 4 || files.some(f => f.size > 5 * 1024 * 1024)) { setError("Attach up to 4 images, at most 5 MB each."); return; }
          setBusy(true);
          try {
            const added = await Promise.all(files.map(file => new Promise<{ name: string; url: string }>((resolve, reject) => {
              const reader = new FileReader(); reader.onload = () => resolve({ name: file.name, url: String(reader.result) });
              reader.onerror = () => reject(new Error("Cannot read image")); reader.readAsDataURL(file);
            })));
            setImages(current => [...current, ...added]);
          } catch (e) { setError((e as Error).message); }
          finally { setBusy(false); }
        }} /></label>}
      </div>
      <div className="composer-bar">
        <select
          value={llmId ?? ""}
          onChange={(e) => onLlmChange(e.target.value)}
          disabled={llms.length === 0 || running || busy}
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
