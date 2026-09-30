import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type LlmEntry, type ModelProfile, type ConnectionStatus } from "../api";
import { useApp } from "../context";
import { agentProvider, providerLabel } from "../modelChoices";

type AuthMethod = "browser" | "api_value" | "api_env";
type Form = {
  id?: string; model_name: string; model: string; api_key: string; env_var: string;
  api_base: string; api_version: string; extra: { key: string; value: string }[]; auth: AuthMethod;
};
const BASIC = ["model", "api_key", "api_base", "api_version"];
const EMPTY: Form = { model_name: "", model: "", api_key: "", env_var: "", api_base: "", api_version: "", extra: [], auth: "api_value" };
const envName = (provider: string) => ({ openai: "OPENAI_API_KEY", anthropic: "ANTHROPIC_API_KEY", openrouter: "OPENROUTER_API_KEY", gemini: "GEMINI_API_KEY" }[provider] ?? "");

function toForm(e: LlmEntry): Form {
  const p = e.litellm_params;
  const str = (k: string) => p[k] == null ? "" : String(p[k]);
  const reference = str("api_key").startsWith("os.environ/");
  return { id: e.id, model_name: e.model_name, model: str("model"), api_key: reference ? "" : str("api_key"),
    env_var: reference ? str("api_key").slice("os.environ/".length) : envName(str("model").split("/")[0]),
    api_base: str("api_base"), api_version: str("api_version"),
    extra: Object.entries(p).filter(([k]) => !BASIC.includes(k)).map(([key, v]) => ({ key, value: typeof v === "string" ? v : JSON.stringify(v) })),
    auth: e.auth_mode === "browser" ? "browser" : reference ? "api_env" : "api_value" };
}
function parseValue(value: string): unknown { try { return JSON.parse(value); } catch { return value; } }
function fromForm(f: Form): Partial<LlmEntry> {
  const params: Record<string, unknown> = { model: f.model.trim() };
  if (f.auth !== "browser") {
    if (f.auth === "api_env") params.api_key = `os.environ/${f.env_var.trim()}`;
    else if (f.api_key) params.api_key = f.api_key;
    if (f.api_base) params.api_base = f.api_base.trim();
    if (f.api_version) params.api_version = f.api_version.trim();
    for (const { key, value } of f.extra) if (key.trim() && !BASIC.includes(key.trim())) params[key.trim()] = parseValue(value);
  }
  return { model_name: f.model_name.trim() || f.model.trim(), litellm_params: params, auth_mode: f.auth === "browser" ? "browser" : "api_key" };
}

export function ConnectionPill({ status }: { status: ConnectionStatus }) {
  return <span className={`badge ${status === "connected" ? "ok" : status === "not_connected" ? "warn" : ""}`}>
    {{ connected: "Connected", not_connected: "Not connected", not_tested: "Not tested" }[status]}
  </span>;
}

export default function AgentForm({ entry, provider, catalog, onClose, onSaved, onBusy }: {
  entry?: LlmEntry; provider: string; catalog: ModelProfile[];
  onClose: () => void; onSaved: (entry: LlmEntry) => void; onBusy: (busy: boolean) => void;
}) {
  const { defaultLlmId, refreshLlms } = useApp();
  const presets = catalog.filter(m => agentProvider(m.model) === provider);
  const [form, setForm] = useState<Form>(() => entry ? toForm(entry) : {
    ...EMPTY, model: provider + "/", env_var: envName(provider),
    auth: ["openai", "anthropic"].includes(provider) ? "browser" : "api_env",
  });
  const [status, setStatus] = useState<ConnectionStatus>(entry?.connection_status ?? "not_tested");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [environmentNames, setEnvironmentNames] = useState<string[]>([]);
  const formRef = useRef<HTMLFormElement>(null);
  useEffect(() => {
    let active = true;
    api.providerModels(provider).then(r => { if (active) setSuggestions(r.models); }).catch(() => {});
    api.environment().then(r => { if (active) setEnvironmentNames(r.variables.map(v => v.name)); }).catch(() => {});
    return () => { active = false; };
  }, [provider]);
  useEffect(() => { formRef.current?.scrollIntoView({ block: "nearest" }); }, []);
  const set = (patch: Partial<Form>) => {
    setForm(f => ({ ...f, ...patch })); setStatus("not_tested"); setMessage(""); setError("");
  };
  const lock = (value: boolean) => { setBusy(value); onBusy(value); };
  async function persist() {
    if (agentProvider(form.model) !== provider) throw new Error(`Choose an agent from ${providerLabel(provider)}.`);
    const saved = form.id ? await api.updateLlm(form.id, fromForm(form)) : await api.createLlm(fromForm(form));
    setForm(toForm(saved)); onSaved(saved); refreshLlms();
    return saved;
  }
  async function save(event: FormEvent) {
    event.preventDefault(); lock(true); setError("");
    try { await persist(); onClose(); }
    catch (e) { setError((e as Error).message); }
    finally { lock(false); }
  }
  async function test() {
    if (!formRef.current?.reportValidity()) return;
    lock(true); setTesting(true); setError(""); setMessage("");
    try {
      const saved = await persist();
      const result = await api.testLlm(saved.id);
      setStatus(result.connection_status);
      setMessage(result.ok ? result.reply || "Connection successful." : result.error || "Connection failed.");
      refreshLlms();
    } catch (e) { setStatus("not_tested"); setError((e as Error).message); }
    finally { lock(false); setTesting(false); }
  }
  async function remove() {
    if (!form.id || !confirm(`Delete "${form.model_name || form.model}"?`)) return;
    lock(true); setError("");
    try { await api.deleteLlm(form.id); refreshLlms(); onClose(); }
    catch (e) { setError((e as Error).message); }
    finally { lock(false); }
  }
  function preset(model: string) {
    const chosen = presets.find(p => p.model === model); if (!chosen) return;
    set({ model: chosen.model, model_name: chosen.name });
  }
  return <form ref={formRef} className="panel llm-form" onSubmit={save} aria-label={entry ? `Edit ${entry.model_name}` : `Add ${providerLabel(provider)} agent`}>
    <header className="agent-form-head"><div><h3>{form.id ? form.model_name || "Edit agent" : "Add agent"}</h3><ConnectionPill status={status} /></div>
      {form.id && <button type="button" className="danger-text" disabled={busy} onClick={remove}>Delete</button>}
    </header>
    <fieldset className="agent-fields" disabled={busy}>
      <label><span>Agent presets</span><select aria-label="Agent presets" value={presets.some(p => p.model === form.model) ? form.model : ""} onChange={e => preset(e.target.value)}>
        <option value="">{form.model !== provider + "/" ? "Custom agent" : "Choose an agent…"}</option>
        {presets.map(m => <option key={m.model} value={m.model}>{m.name}</option>)}
      </select></label>
      <label><span>Model ID</span><input aria-label="Model ID" required list="model-suggestions" value={form.model} onChange={e => set({ model: e.target.value })} />
        <datalist id="model-suggestions">{suggestions.map(m => <option key={m} value={m} />)}</datalist>
        <small className="muted">Only {providerLabel(provider)} models with tools and image input are supported.</small>
      </label>
      <label><span>Display name</span><input value={form.model_name} placeholder="Shown in the agent picker" onChange={e => set({ model_name: e.target.value })} /></label>
      <label><span>Authentication</span><select aria-label="Authentication" value={form.auth} onChange={e => set({ auth: e.target.value as AuthMethod, env_var: form.env_var || envName(provider) })}>
        {["openai", "anthropic"].includes(provider) && <option value="browser">Browser login</option>}
        <option value="api_value">API key (value)</option><option value="api_env">API key (env var)</option>
      </select></label>
      {form.auth === "browser" ? <p className="muted small">Uses the account connected in Browser login above.</p> : <>
        {form.auth === "api_env" ? <label><span>Environment variable</span>
          <input aria-label="Environment variable" required list="environment-names" pattern="[A-Za-z_][A-Za-z0-9_]*" autoComplete="off" spellCheck={false} value={form.env_var}
            placeholder={envName(provider) || "MY_API_KEY"} onChange={e => set({ env_var: e.target.value })} />
          <datalist id="environment-names">{environmentNames.map(name => <option key={name}>{name}</option>)}</datalist>
          <small className="muted">Uses the saved environment value first, then the container’s environment.</small>
        </label> : <label><span>API key value</span><input aria-label="API key value" type="password" autoComplete="new-password" spellCheck={false} value={form.api_key} placeholder="Paste your API key" onChange={e => set({ api_key: e.target.value })} />
          <small className="muted">Leave the masked value unchanged to keep the saved key.</small>
        </label>}
        <details className="advanced-model-settings"><summary>Connection and advanced parameters</summary>
          <div className="row">
            <label><span>API base URL</span><input value={form.api_base} placeholder="Optional" onChange={e => set({ api_base: e.target.value })} /></label>
            <label><span>API version</span><input value={form.api_version} placeholder="Optional (Azure)" onChange={e => set({ api_version: e.target.value })} /></label>
          </div>
          <fieldset><legend>Extra LiteLLM parameters</legend>
            <small className="muted">Use parameters supported by this agent. JSON values are parsed.</small>
            {form.extra.map((row, i) => <div className="row extra-row" key={i}>
              <input aria-label={`Parameter name ${i + 1}`} placeholder="Name" value={row.key} onChange={e => set({ extra: form.extra.map((r, j) => j === i ? { ...r, key: e.target.value } : r) })} />
              <input aria-label={`Parameter value ${i + 1}`} type={/key|secret|token|password|credential|authorization|extra_headers/i.test(row.key) ? "password" : "text"} autoComplete="off" placeholder="Value" value={row.value} onChange={e => set({ extra: form.extra.map((r, j) => j === i ? { ...r, value: e.target.value } : r) })} />
              <button type="button" className="icon-button" aria-label={`Remove parameter ${i + 1}`} onClick={() => set({ extra: form.extra.filter((_, j) => j !== i) })}>✕</button>
            </div>)}
            <button type="button" onClick={() => set({ extra: [...form.extra, { key: "", value: "" }] })}>+ Parameter</button>
          </fieldset>
        </details>
      </>}
    </fieldset>
    {error && <div className="banner error" role="alert">{error}</div>}
    {message && <p className={`small ${status === "connected" ? "ok-text" : "warn-text"}`} role="status">{message}</p>}
    <div className="agent-test-row"><button type="button" disabled={busy} onClick={test}>{testing ? "Testing…" : "Test"}</button><small className="muted">Saves these settings before testing the connection.</small></div>
    <div className="form-actions">
      {form.id && form.id !== defaultLlmId && <button type="button" disabled={busy} onClick={() => {
        lock(true); api.defaultLlm(form.id!).then(refreshLlms).catch(e => setError(e.message)).finally(() => lock(false));
      }}>Make default</button>}
      <button type="button" disabled={busy} onClick={onClose}>Close</button>
      <button type="submit" className="primary" disabled={busy}>{busy && !testing ? "Saving…" : "Save agent"}</button>
    </div>
  </form>;
}
