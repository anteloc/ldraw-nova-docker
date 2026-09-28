import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type LlmEntry, type ModelProfile } from "../api";
import ProviderLogin from "../components/ProviderLogin";
import EnvironmentSettings from "../components/EnvironmentSettings";
import { useApp } from "../context";
import { providerName } from "../modelChoices";

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

export default function Settings() {
  const { llms, defaultLlmId, refreshLlms } = useApp();
  const [form, setForm] = useState<Form | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [tests, setTests] = useState<Record<string, { ok: boolean; text: string } | "running">>({});
  const [error, setError] = useState<string | null>(null);
  const [yaml, setYaml] = useState("");
  const [importMsg, setImportMsg] = useState<string | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [catalog, setCatalog] = useState<ModelProfile[]>([]);
  const [busy, setBusy] = useState(false);
  const [environmentNames, setEnvironmentNames] = useState<string[]>([]);
  const importFile = useRef<HTMLInputElement>(null);
  const provider = form?.model.split("/")[0] ?? "";

  useEffect(() => { api.catalog().then(r => setCatalog(r.models)).catch(e => setError(e.message)); }, []);
  useEffect(() => {
    let active = true;
    setSuggestions([]);
    if (provider) api.providerModels(provider).then(r => { if (active) setSuggestions(r.models); }).catch(() => {});
    return () => { active = false; };
  }, [provider]);
  useEffect(() => {
    if (form?.auth === "api_env") api.environment().then(r => setEnvironmentNames(r.variables.map(v => v.name))).catch(() => {});
  }, [form?.auth]);
  const set = (patch: Partial<Form>) => setForm(f => f ? { ...f, ...patch } : f);

  async function save(e: FormEvent) {
    e.preventDefault(); if (!form) return;
    setError(null); setBusy(true);
    try {
      const entry = fromForm(form);
      if (form.id) await api.updateLlm(form.id, entry); else await api.createLlm(entry);
      setForm(null); refreshLlms();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function edit(entry: LlmEntry) {
    setError(null); setBusy(true); setShowImport(false);
    try { setForm(toForm(await api.editLlm(entry.id))); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function test(id: string) {
    setTests(t => ({ ...t, [id]: "running" }));
    const r = await api.testLlm(id).catch(e => ({ ok: false, error: (e as Error).message, reply: undefined }));
    setTests(t => ({ ...t, [id]: { ok: r.ok, text: r.ok ? `Replied: ${r.reply ?? ""}` : r.error ?? "failed" } }));
  }
  async function remove(entry: LlmEntry) {
    if (!confirm(`Delete "${entry.model_name}"?`)) return;
    try { await api.deleteLlm(entry.id); refreshLlms(); }
    catch (e) { setError((e as Error).message); }
  }
  async function importYaml() {
    setImportMsg(null); setError(null); setBusy(true);
    try {
      const r = await api.importLlm(yaml);
      setImportMsg(`Imported ${r.imported.length} model(s).`); setYaml(""); refreshLlms();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  function preset(model: string) {
    const p = catalog.find(m => m.model === model); if (!p || !form) return;
    const nextProvider = p.model.split("/")[0];
    const router = nextProvider === "openrouter";
    set({ model: p.model, model_name: p.name, auth: router ? "api_env" : "browser", env_var: envName(nextProvider),
      api_key: nextProvider === provider ? form.api_key : "", api_base: "", api_version: "", extra: [] });
  }

  return <div className="page settings">
    <header className="page-head"><div><h1>Settings</h1><p className="muted">Connect your accounts and choose the agents you build with.</p></div></header>
    <section aria-labelledby="browser-login-heading">
      <h2 id="browser-login-heading" className="settings-heading">Browser login</h2>
      <div className="provider-logins"><ProviderLogin provider="openai" /><ProviderLogin provider="anthropic" /></div>
    </section>
    <EnvironmentSettings />
    <section aria-labelledby="models-heading">
      <header className="page-head settings-models-head">
        <div><h2 id="models-heading">Models</h2><p className="muted small">Models with tools and vision for planning, building and reviewing your creations.</p></div>
        <div className="head-actions">
          <button type="button" aria-expanded={showImport} aria-controls="model-import" disabled={busy} onClick={() => { setShowImport(!showImport); setError(null); }}>Import / export</button>
          <button type="button" className="primary" disabled={busy} onClick={() => { setForm({ ...EMPTY }); setShowImport(false); setError(null); }}>+ Add model</button>
        </div>
      </header>
      {error && <div className="banner error" role="alert">{error}</div>}
      {showImport && <section id="model-import" className="panel import" aria-label="Import and export models">
        <h3>Add several models at once</h3>
        <p className="muted small">Paste a LiteLLM model list or open a YAML file. Models must support tools and images. Exported API-key values are masked; environment references can be reused.</p>
        <div className="head-actions">
          <button type="button" onClick={() => importFile.current?.click()}>Open YAML file</button>
          <input ref={importFile} type="file" accept=".yaml,.yml,text/yaml" hidden onChange={async e => {
            const file = e.target.files?.[0]; e.target.value = "";
            if (!file) return;
            if (file.size > 1024 * 1024) { setError("Choose a YAML file smaller than 1 MB."); return; }
            try { setYaml(await file.text()); } catch { setError("Could not read that file."); }
          }} />
          <a className="button" href="/api/llm-models/export" download="models.yaml">Export models</a>
        </div>
        <textarea rows={7} aria-label="Model list YAML" value={yaml} onChange={e => setYaml(e.target.value)}
          placeholder={'model_list:\n  - model_name: GPT-6 Sol\n    litellm_params:\n      model: openrouter/openai/gpt-6-sol\n      api_key: os.environ/OPENROUTER_API_KEY'} />
        <div className="form-actions">{importMsg && <span className="small ok-text" role="status">{importMsg}</span>}
          <button type="button" onClick={() => setShowImport(false)}>Close</button>
          <button type="button" className="primary" disabled={!yaml.trim() || busy} onClick={importYaml}>{busy ? "Importing…" : "Import models"}</button>
        </div>
      </section>}
      {form && <form className="panel llm-form" onSubmit={save}>
        <h3>{form.id ? "Edit model" : "Add model"}</h3>
        <label><span>Model presets</span><select aria-label="Model presets" value={catalog.some(p => p.model === form.model) ? form.model : ""} onChange={e => preset(e.target.value)}>
          <option value="">{form.model ? "Custom model" : "Choose a model…"}</option>
          {catalog.map(m => <option key={m.model} value={m.model}>{m.name}</option>)}
        </select></label>
        {!form.id && <div className="presets">{["openai", "anthropic", "openrouter", "gemini", "ollama_chat"].map(p =>
          <button type="button" key={p} onClick={() => set({ ...EMPTY, model: p + "/", env_var: envName(p), auth: "api_env",
            ...(p === "ollama_chat" ? { auth: "api_value", api_base: "http://host.docker.internal:11434" } : {}) })}>
            {{ openai: "OpenAI", anthropic: "Claude", openrouter: "OpenRouter", gemini: "Gemini", ollama_chat: "Ollama" }[p]}
          </button>)}</div>}
        <label><span>Model ID</span><input aria-label="Model ID" required list="model-suggestions" placeholder="provider/model" value={form.model} onChange={e => {
          const model = e.target.value; const p = model.split("/")[0];
          set({ model, ...(form.auth === "browser" && !["openai", "anthropic", "chatgpt"].includes(p) ? { auth: "api_env" as const, env_var: envName(p) } : {}) });
        }} />
          <datalist id="model-suggestions">{suggestions.map(m => <option key={m} value={m} />)}</datalist>
          <small className="muted">Suggestions include only models with verified tool and image support.</small>
        </label>
        <label><span>Display name</span><input value={form.model_name} placeholder="Shown in the model picker" onChange={e => set({ model_name: e.target.value })} /></label>
        <label><span>Authentication</span><select aria-label="Authentication" value={form.auth} onChange={e => set({ auth: e.target.value as AuthMethod, env_var: form.env_var || envName(provider) })}>
          {["openai", "anthropic", "chatgpt"].includes(provider) && <option value="browser">Browser login</option>}
          <option value="api_value">API key (value)</option><option value="api_env">API key (env var)</option>
        </select></label>
        {form.auth === "browser" ? <p className="muted small">Uses the account connected in Browser login above.</p> : <>
          {form.auth === "api_env" ? <label><span>Environment variable</span>
            <input aria-label="Environment variable" aria-describedby="key-env-hint" required list="environment-names" pattern="[A-Za-z_][A-Za-z0-9_]*" autoComplete="off" spellCheck={false} value={form.env_var}
              placeholder={envName(provider) || "MY_API_KEY"} onChange={e => set({ env_var: e.target.value })} />
            <datalist id="environment-names">{environmentNames.map(name => <option key={name}>{name}</option>)}</datalist>
            <small id="key-env-hint" className="muted">Uses the saved value in Environment variables first, then the inherited environment.</small>
          </label> : <label><span>API key value</span><input type="text" autoComplete="off" spellCheck={false} value={form.api_key} placeholder="Paste your API key" onChange={e => set({ api_key: e.target.value })} /></label>}
          <details className="advanced-model-settings"><summary>Connection and advanced parameters</summary>
            <div className="row">
              <label><span>API base URL</span><input value={form.api_base} placeholder="Optional" onChange={e => set({ api_base: e.target.value })} /></label>
              <label><span>API version</span><input value={form.api_version} placeholder="Optional (Azure)" onChange={e => set({ api_version: e.target.value })} /></label>
            </div>
            <fieldset><legend>Extra LiteLLM parameters</legend>
              <small className="muted">Use parameters supported by this model. JSON values are parsed.</small>
              {form.extra.map((row, i) => <div className="row extra-row" key={i}>
                <input aria-label={`Parameter name ${i + 1}`} placeholder="Name" value={row.key} onChange={e => set({ extra: form.extra.map((r, j) => j === i ? { ...r, key: e.target.value } : r) })} />
                <input aria-label={`Parameter value ${i + 1}`} placeholder="Value" value={row.value} onChange={e => set({ extra: form.extra.map((r, j) => j === i ? { ...r, value: e.target.value } : r) })} />
                <button type="button" className="icon-button" aria-label={`Remove parameter ${i + 1}`} onClick={() => set({ extra: form.extra.filter((_, j) => j !== i) })}>✕</button>
              </div>)}
              <button type="button" onClick={() => set({ extra: [...form.extra, { key: "", value: "" }] })}>+ Parameter</button>
            </fieldset>
          </details>
        </>}
        <div className="form-actions"><button type="button" disabled={busy} onClick={() => { setForm(null); setError(null); }}>Cancel</button>
          <button type="submit" className="primary" disabled={busy}>{busy ? "Saving…" : "Save model"}</button></div>
      </form>}
      <div className="llm-list">
        {!llms.length && !form && <p className="muted">Add a model to start building.</p>}
        {llms.map(m => {
          const t = tests[m.id]; const environment = String(m.litellm_params.api_key ?? "").startsWith("os.environ/");
          return <div key={m.id} className="panel llm-row">
            <div className="llm-info"><div className="llm-title"><strong>{m.model_name}</strong>{m.id === defaultLlmId && <span className="badge">default</span>}
              <span className="badge">{providerName(m)}</span><span className="badge">{m.auth_mode === "browser" ? "Browser login" : environment ? "API key · env var" : "API key · value"}</span></div>
              <div className="muted small model-id">{String(m.litellm_params.model)}</div>
              {t && <div className={`small ${t === "running" ? "muted" : t.ok ? "ok-text" : "warn-text"}`}>{t === "running" ? "Testing…" : t.text}</div>}
            </div>
            <div className="llm-actions"><button disabled={t === "running"} onClick={() => test(m.id)}>Test</button>
              <button disabled={busy} onClick={() => edit(m)}>Edit</button>
              {m.id !== defaultLlmId && <button onClick={() => api.defaultLlm(m.id).then(refreshLlms).catch(e => setError(e.message))}>Make default</button>}
              <button className="danger-text" onClick={() => remove(m)}>Delete</button>
            </div>
          </div>;
        })}
      </div>
    </section>
  </div>;
}
