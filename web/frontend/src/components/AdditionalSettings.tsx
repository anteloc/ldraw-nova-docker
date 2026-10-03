import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { TurnOptions } from "../api";

const sculptureExample = new URL("../assets/sculpture-example.png", import.meta.url).href;

export default function AdditionalSettings({ options, onChange, disabled }: {
  options: TurnOptions; onChange: (options: TurnOptions) => void; disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [info, setInfo] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [position, setPosition] = useState({ left: 12, top: 0, width: 320, maxHeight: 480, transform: "none" });
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const checkbox = useRef<HTMLInputElement>(null);
  const infoButton = useRef<HTMLButtonElement>(null);
  const id = useId();
  const helpId = useId();

  useLayoutEffect(() => {
    if (!open) return;
    function reposition() {
      const rect = trigger.current!.getBoundingClientRect();
      const width = Math.min(320, window.innerWidth - 24);
      const above = rect.top > window.innerHeight - rect.bottom;
      setPosition({ left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)),
        top: above ? rect.top - 8 : rect.bottom + 8, width,
        maxHeight: Math.max(80, (above ? rect.top : window.innerHeight - rect.bottom) - 20),
        transform: above ? "translateY(-100%)" : "none" });
    }
    reposition();
    checkbox.current?.focus();
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => { window.removeEventListener("resize", reposition); window.removeEventListener("scroll", reposition, true); };
  }, [open]);

  useEffect(() => {
    if (!open) { setInfo(false); setPinned(false); return; }
    function outside(e: Event) {
      if (!panel.current?.contains(e.target as Node) && !trigger.current?.contains(e.target as Node)) setOpen(false);
    }
    function escape(e: KeyboardEvent) {
      if (e.key === "Escape") { e.preventDefault(); setOpen(false); trigger.current?.focus(); }
    }
    document.addEventListener("pointerdown", outside);
    document.addEventListener("focusin", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside); document.removeEventListener("focusin", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  useEffect(() => { if (disabled) setOpen(false); }, [disabled]);

  return <>
    <button ref={trigger} type="button" className="compact-control additional-settings-trigger" disabled={disabled}
      aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? id : undefined} onClick={() => setOpen(!open)}>
      Additional settings<span className="chevron" aria-hidden>⌄</span>
    </button>
    {open && createPortal(<div ref={panel} id={id} role="dialog" aria-label="Additional settings"
      className={`additional-settings-panel${position.transform !== "none" ? " is-above" : ""}`} style={position}
      onMouseLeave={() => { if (!pinned && document.activeElement !== infoButton.current) setInfo(false); }}>
      <div className="sculpture-setting">
        <label className="sculpture-option">
          <input ref={checkbox} type="checkbox" checked={options.build_style === "sculpture"} disabled={disabled}
            onChange={e => onChange({ ...options, build_style: e.target.checked ? "sculpture" : "parts" })} />
          3D sculpture
        </label>
        <button ref={infoButton} type="button" className="sculpture-info-button" aria-label="About 3D sculpture"
          aria-expanded={info} aria-controls={info ? helpId : undefined}
          onMouseEnter={() => setInfo(true)}
          onFocus={() => setInfo(true)} onBlur={() => { if (!pinned) setInfo(false); }}
          onClick={() => { setPinned(!pinned); setInfo(!pinned); }}>i</button>
      </div>
      {info && <div id={helpId} className="sculpture-help" role="region" aria-label="About 3D sculpture">
        <img src={sculptureExample} width="1000" height="800" alt="An owl sculpture built from connected brown, white and yellow LEGO bricks on a gray base" />
        <p>Turn a 3D voxel shape into a LEGO sculpture, with connected bricks and ordered building steps.</p>
        <p>Voxel builds can be quicker than detailed part-by-part builds. Estimated time: around 1–2 minutes for simple sculptures; size and AI model speed affect timing.</p>
        <p>You can also use a voxel editor: export the shape as voxel JSON and attach it to your prompt. The agent can adapt it to the sculpture input format.</p>
        <small className="muted">Example generated with this mode: an owl with 272 bricks.</small>
      </div>}
    </div>, document.body)}
  </>;
}
