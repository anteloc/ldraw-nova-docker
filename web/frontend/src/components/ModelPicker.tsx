import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { useApp } from "../context";
import { providerName, recentModels, rememberModel } from "../modelChoices";
import type { LlmEntry } from "../api";

export default function ModelPicker({ value, onChange, disabled }: {
  value: string | null; onChange: (id: string) => void; disabled: boolean;
}) {
  const { llms, chats } = useApp();
  const [open, setOpen] = useState(false);
  const [recent, setRecent] = useState(recentModels);
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState<string | null>(null);
  const [position, setPosition] = useState({ left: 0, top: 0, width: 340, maxHeight: 420, transform: "none" });
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const id = useId();
  const selected = llms.find(m => m.id === value);
  const groups = [...new Set(llms.map(providerName))];
  const recentIds = [...new Set([...recent, ...chats.map(c => c.llm_model_id).filter((id): id is string => !!id)])];
  const recentEntries = recentIds.map(id => llms.find(m => m.id === id)).filter((m): m is LlmEntry => !!m).slice(0, 4);
  const matches = llms.filter(m => `${m.model_name} ${providerName(m)} ${m.litellm_params.model}`.toLowerCase().includes(query.toLowerCase()));

  useLayoutEffect(() => {
    if (!open) return;
    function reposition() {
      const rect = trigger.current!.getBoundingClientRect();
      const width = Math.min(340, window.innerWidth - 24);
      const above = rect.top > window.innerHeight - rect.bottom;
      const maxHeight = Math.min(480, (above ? rect.top : window.innerHeight - rect.bottom) - 20);
      setPosition({ left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)),
        top: above ? rect.top - 8 : rect.bottom + 8, width, maxHeight, transform: above ? "translateY(-100%)" : "none" });
    }
    reposition();
    search.current?.focus();
    window.addEventListener("resize", reposition);
    return () => window.removeEventListener("resize", reposition);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function outside(e: PointerEvent) {
      if (!panel.current?.contains(e.target as Node) && !trigger.current?.contains(e.target as Node)) setOpen(false);
    }
    function focusOutside(e: FocusEvent) {
      if (!panel.current?.contains(e.target as Node) && !trigger.current?.contains(e.target as Node)) setOpen(false);
    }
    function escape(e: KeyboardEvent) {
      if (e.key === "Escape") { e.preventDefault(); setOpen(false); trigger.current?.focus(); }
    }
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    document.addEventListener("focusin", focusOutside);
    return () => {
      document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape);
      document.removeEventListener("focusin", focusOutside);
    };
  }, [open]);
  useEffect(() => { if (disabled) setOpen(false); }, [disabled]);

  function choose(model: LlmEntry) {
    setRecent(rememberModel(model.id)); onChange(model.id); setOpen(false); trigger.current?.focus();
  }
  function option(model: LlmEntry) {
    return <button type="button" className="model-choice" key={model.id} onClick={() => choose(model)} aria-pressed={model.id === value}>
      <span><strong>{model.model_name}</strong><small>{providerName(model)} · {model.auth_mode === "browser" ? "Browser login" : "API key"}</small></span>
      {model.id === value && <span aria-hidden>✓</span>}
    </button>;
  }

  return <>
    <button ref={trigger} type="button" className="model-picker-trigger compact-control" disabled={disabled}
      aria-label={`Model: ${selected?.model_name ?? "Choose a model"}`} aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? id : undefined}
      onClick={() => { setOpen(!open); setQuery(""); setProvider(null); setRecent(recentModels()); }}>
      <span className="ellipsis">{selected?.model_name ?? "Choose a model"}</span><span className="chevron" aria-hidden>⌄</span>
    </button>
    {open && createPortal(<div ref={panel} id={id} role="dialog" aria-label="Choose a model" className="model-picker-panel" style={position}>
      <input ref={search} type="search" aria-label="Search models" placeholder="Search your models…" value={query} onChange={e => setQuery(e.target.value)} />
      <div className="model-picker-options">
        {query ? <>{matches.map(option)}{!matches.length && <p className="muted small pad">No matching models.</p>}</> : <>
          {!!recentEntries.length && <><div className="picker-label">Recent</div>{recentEntries.map(option)}</>}
          <div className="picker-label">Providers</div>
          {groups.map(name => <div key={name}>
            <button className="provider-choice" type="button" aria-expanded={provider === name} onClick={() => setProvider(provider === name ? null : name)}>
              <span>{name}</span><span className="muted">{llms.filter(m => providerName(m) === name).length} <span aria-hidden>{provider === name ? "⌄" : "›"}</span></span>
            </button>
            {provider === name && <div className="provider-models">{llms.filter(m => providerName(m) === name).map(option)}</div>}
          </div>)}
        </>}
      </div>
      <Link className="picker-settings" to="/settings" onClick={() => setOpen(false)}>Manage models</Link>
    </div>, document.body)}
  </>;
}
