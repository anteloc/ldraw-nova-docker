import { useEffect, useState } from "react";
import { api, type ModelProfile } from "../api";
import ProviderLogin from "../components/ProviderLogin";
import EnvironmentSettings from "../components/EnvironmentSettings";
import AgentForm, { ConnectionPill } from "../components/AgentForm";
import { useApp } from "../context";
import { agentProvider, providerLabel } from "../modelChoices";

export default function Settings() {
  const { llms, defaultLlmId } = useApp();
  const [catalog, setCatalog] = useState<ModelProfile[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [newId, setNewId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api.catalog().then(r => setCatalog(r.models)).catch(e => setError(e.message)); }, []);
  const providers = [...new Set(["anthropic", "openai", "openrouter", ...llms.map(m => agentProvider(String(m.litellm_params.model)))])];
  const close = () => { setEditing(null); setNewId(null); };
  return <div className="page settings">
    <header className="page-head"><div><h1>Settings</h1><p className="muted">Connect your accounts and choose the agents you build with.</p></div></header>
    <section aria-labelledby="browser-login-heading">
      <h2 id="browser-login-heading" className="settings-heading">Browser login</h2>
      <div className="provider-logins"><ProviderLogin provider="openai" /><ProviderLogin provider="anthropic" /></div>
    </section>
    <EnvironmentSettings />
    <section aria-labelledby="agents-heading">
      <header className="page-head settings-models-head"><div><h2 id="agents-heading">Agents</h2><p className="muted small">Agents with tools and vision for planning, building and reviewing your creations.</p></div></header>
      {error && <div className="banner error" role="alert">{error}</div>}
      <div className="agent-providers">{providers.map(provider => {
        const entries = llms.filter(m => agentProvider(String(m.litellm_params.model)) === provider);
        const open = expanded === provider;
        return <section className="agent-provider" key={provider} aria-label={`${providerLabel(provider)} agents`}>
          <header className="agent-provider-head">
            <button type="button" className="provider-toggle" disabled={busy} aria-expanded={open} aria-controls={`agents-${provider}`} onClick={() => { setExpanded(open ? null : provider); close(); }}>
              <span className="provider-chevron" aria-hidden>{open ? "⌄" : "›"}</span><strong>{providerLabel(provider)}</strong><span className="badge">{entries.length}</span>
            </button>
            <button type="button" disabled={busy} onClick={() => { setExpanded(provider); setEditing("new"); setNewId(null); }}>+ Add agent</button>
          </header>
          {open && <div id={`agents-${provider}`} className="agent-provider-body">
            {editing === "new" && <AgentForm key={`new-${provider}`} provider={provider} catalog={catalog} onClose={close} onSaved={entry => setNewId(entry.id)} onBusy={setBusy} />}
            <div className="llm-list">
              {entries.filter(m => !(editing === "new" && m.id === newId)).map(m => editing === m.id ?
                <AgentForm key={m.id} entry={m} provider={provider} catalog={catalog} onClose={close} onSaved={() => {}} onBusy={setBusy} /> :
                <div key={m.id} className="panel llm-row">
                  <div className="llm-info"><div className="llm-title"><strong>{m.model_name}</strong>
                    {m.id === defaultLlmId && <span className="badge">Default</span>}
                    <span className="badge">{m.auth_mode === "browser" ? "Browser login" : String(m.litellm_params.api_key ?? "").startsWith("os.environ/") ? "API key · env var" : "API key · value"}</span>
                    <ConnectionPill status={m.connection_status ?? "not_tested"} />
                  </div><div className="muted small model-id">{String(m.litellm_params.model)}</div></div>
                  <div className="llm-actions"><button type="button" disabled={busy} onClick={() => { setEditing(m.id); setNewId(null); }}>Edit</button></div>
                </div>
              )}
              {!entries.length && editing !== "new" && <p className="muted small">No agents configured for {providerLabel(provider)} yet.</p>}
            </div>
          </div>}
        </section>;
      })}</div>
    </section>
  </div>;
}
