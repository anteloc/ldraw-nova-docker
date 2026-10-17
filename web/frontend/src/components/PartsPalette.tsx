import { useEffect, useRef, useState } from "react";
import { api, type PartsPaletteInfo } from "../api";

export default function PartsPalette({ chatId, running = false, onChange, onSelection, onBusy }: {
  chatId?: string; running?: boolean;
  onChange?: (csv: string | null) => void;
  onSelection?: (enabled: boolean) => void;
  onBusy: (busy: boolean) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [info, setInfo] = useState<PartsPaletteInfo>({ enabled: false, allowed_combinations: null });
  const [filename, setFilename] = useState("");
  const [busy, setBusy] = useState(!!chatId);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!chatId) return;
    let active = true;
    setBusy(true); onBusy(true);
    api.partsPalette(chatId).then(value => { if (active) setInfo(value); })
      .catch(e => { if (active) setError((e as Error).message); })
      .finally(() => { if (active) { setBusy(false); onBusy(false); } });
    return () => { active = false; };
  }, [chatId, onBusy]);

  async function upload(file: File) {
    setError("");
    if (!/\.(csv|ldr|mpd|xml|io)$/i.test(file.name) || !file.size || file.size > 16 * 1024 * 1024) {
      setError("Choose an LDR, CSV, XML, or Studio IO file no larger than 16 MB."); return;
    }
    setBusy(true); onBusy(true);
    try {
      const imported = await api.importPalette(file);
      const { csv } = imported;
      const updated = chatId ? await api.savePalette(chatId, csv) : imported;
      setInfo(updated); setFilename(file.name); onChange?.(csv); onSelection?.(true);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); onBusy(false); }
  }
  async function select(enabled: boolean) {
    setError(""); setBusy(true); onBusy(true);
    try {
      setInfo(chatId ? await api.selectPalette(chatId, enabled) : { ...info, enabled });
      onSelection?.(enabled);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); onBusy(false); }
  }
  async function clear() {
    setError(""); setBusy(true); onBusy(true);
    try {
      setInfo(chatId ? await api.clearPalette(chatId) : { enabled: false, allowed_combinations: null });
      setFilename(""); onChange?.(null); onSelection?.(true);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); onBusy(false); }
  }
  const restricted = info.allowed_combinations != null;
  return <section className="parts-palette" aria-label="Parts palette">
    <div className="palette-row">
      <div className="palette-status" role="status" aria-live="polite">
        <strong>Parts palette</strong>
        <span className="muted">{busy ? "Checking palette…" : restricted
          ? `${info.enabled ? "Restricted to" : "Palette saved ·"} ${info.allowed_combinations!.toLocaleString()} part/color pairs${filename ? ` · ${filename}` : ""}`
          : "No uploaded palette"}</span>
      </div>
      <div className="palette-actions">
        <input ref={input} type="file" accept=".ldr,.mpd,.csv,.xml,.io" hidden disabled={busy || running}
          aria-label="Upload parts palette" onChange={e => {
            const file = e.target.files?.[0]; e.target.value = ""; if (file) void upload(file);
          }} />
        <button type="button" disabled={busy || running} onClick={() => input.current?.click()}>
          {restricted ? "Replace palette" : "Upload palette"}</button>
        {restricted && <button type="button" disabled={busy || running} onClick={() => void clear()}>
          Remove palette</button>}
      </div>
    </div>
    {restricted && <label className="palette-toggle">
      <input type="checkbox" checked={info.enabled} disabled={busy || running} onChange={e => void select(e.target.checked)} />
      <span>Only use this parts palette</span>
    </label>}
    <small className="muted">Upload LDraw (.ldr), CSV, BrickLink XML, or Studio (.io). Parts, colors and quantities limit generation.{" "}
      <a href="/api/parts-palette/example" download>Download an example</a>.</small>
    {error && <div className="banner error" role="alert">{error}</div>}
  </section>;
}
