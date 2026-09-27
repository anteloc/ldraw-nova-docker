import { useEffect, useState, type FormEvent } from "react";
import { api, type Capability, type LlmEntry, type ModelProfile } from "../api";
import ProviderLogin from "../components/ProviderLogin";
import EnvironmentSettings from "../components/EnvironmentSettings";
import { useApp } from "../context";

type CapChoice = "auto" | "yes" | "no";
type Form = {
  id?: string;
  model_name: string;
  model: string;
  api_key: string;
  api_base: string;
  api_version: string;
  extra: { key: string; value: string }[];
  tools: CapChoice;
  vision: CapChoice;
  auth_mode: "browser" | "api_key";
};

const BASIC = ["model", "api_key", "api_base", "api_version"];
const OPENROUTER_KEY = "os.environ/OPENROUTER_LDRAW_ASTRA_API_KEY";

const EMPTY: Form = {
  model_name: "", model: "", api_key: "", api_base: "", api_version: "", extra: [], tools: "auto", vision: "auto", auth_mode: "api_key",
};

// Starting points only: any LiteLLM model string works (https://docs.litellm.ai/docs/providers).
const PRESETS: { label: string; form: Partial<Form> }[] = [
  { label: "Anthropic", form: { model_name: "Claude Sonnet 5", model: "anthropic/claude-sonnet-5" } },
  { label: "OpenAI", form: { model_name: "", model: "openai/" } },
  { label: "Gemini", form: { model_name: "", model: "gemini/" } },
  { label: "OpenRouter", form: { model_name: "GPT-6 Luna (OpenRouter)", model: "openrouter/openai/gpt-6-luna", api_key: OPENROUTER_KEY } },
  {
    label: "Ollama (on this computer)",
    form: { model_name: "", model: "ollama_chat/", api_base: "http://host.docker.internal:11434" },
  },
  {
    label: "OpenAI-compatible server",
    form: { model_name: "", model: "openai/", api_base: "http://host.docker.internal:1234/v1" },
  },
];

const toChoice = (c: Capability): CapChoice => (c === true ? "yes" : c === false ? "no" : "auto");
const fromChoice = (c: CapChoice): Capability => (c === "yes" ? true : c === "no" ? false : "auto");

function toForm(e: LlmEntry): Form {
  const p = e.litellm_params;
  const str = (k: string) => (p[k] == null ? "" : String(p[k]));
  return {
    id: e.id,
    model_name: e.model_name,
    model: str("model"),
    api_key: str("api_key"),
    api_base: str("api_base"),
    api_version: str("api_version"),
    extra: Object.entries(p)
      .filter(([k]) => !BASIC.includes(k))
      .map(([key, v]) => ({ key, value: typeof v === "string" ? v : JSON.stringify(v) })),
    tools: toChoice(e.capabilities.tools),
    vision: toChoice(e.capabilities.vision),
    auth_mode: e.auth_mode ?? "api_key",
  };
}

function parseValue(v: string): unknown {
  try {
    return JSON.parse(v);
  } catch {
    return v;
  }
}

function fromForm(f: Form): Partial<LlmEntry> {
  const params: Record<string, unknown> = { model: f.model.trim() };
  if (f.api_key) params.api_key = f.api_key;
  if (f.api_base) params.api_base = f.api_base.trim();
  if (f.api_version) params.api_version = f.api_version.trim();
  for (const { key, value } of f.extra) if (key.trim()) params[key.trim()] = parseValue(value);
  return {
    model_name: f.model_name.trim() || f.model.trim(),
    litellm_params: params,
    capabilities: { tools: fromChoice(f.tools), vision: fromChoice(f.vision) },
    auth_mode: f.auth_mode,
  };
}

function CapBadge({ label, value }: { label: string; value: boolean | null }) {
  const cls = value === true ? "ok" : value === false ? "warn" : "";
  const mark = value === true ? "✓" : value === false ? "✗" : "?";
  const title = value === null ? "unknown to LiteLLM — set it explicitly if needed" : undefined;
  return (
    <span className={`badge ${cls}`} title={title}>
      {label} {mark}
    </span>
  );
}

export default function Settings() {
  const { llms, defaultLlmId, refreshLlms } = useApp();
  const [form, setForm] = useState<Form | null>(null);
  const [providers, setProviders] = useState<string[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [tests, setTests] = useState<Record<string, { ok: boolean; text: string } | "running">>({});
  const [error, setError] = useState<string | null>(null);
  const [yaml, setYaml] = useState("");
  const [importMsg, setImportMsg] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<ModelProfile[]>([]);

  useEffect(() => {
    api.providers().then((r) => setProviders(r.providers)).catch(() => {});
    api.catalog().then(r => setCatalog(r.models)).catch(e => setError(e.message));
  }, []);

  const provider = form?.model.includes("/") ? form.model.split("/")[0] : "";
  useEffect(() => {
    if (!provider || !providers.includes(provider)) return setSuggestions([]);
    api.providerModels(provider).then((r) => setSuggestions(r.models)).catch(() => setSuggestions([]));
  }, [provider, providers]);

  const set = (patch: Partial<Form>) => setForm((f) => (f ? { ...f, ...patch } : f));

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!form) return;
    setError(null);
    try {
      const entry = fromForm(form);
      if (form.id) await api.updateLlm(form.id, entry);
      else await api.createLlm(entry);
      setForm(null);
      refreshLlms();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function test(id: string) {
    setTests((t) => ({ ...t, [id]: "running" }));
    const r = await api.testLlm(id).catch((e) => ({ ok: false, error: (e as Error).message, reply: undefined }));
    setTests((t) => ({ ...t, [id]: { ok: r.ok, text: r.ok ? `Replied: ${r.reply ?? ""}` : r.error ?? "failed" } }));
  }

  async function remove(entry: LlmEntry) {
    if (!confirm(`Delete "${entry.model_name}"?`)) return;
    await api.deleteLlm(entry.id);
    refreshLlms();
  }

  async function importYaml() {
    setImportMsg(null);
    try {
      const r = await api.importLlm(yaml);
      setImportMsg(`Imported ${r.imported.length} model(s).`);
      setYaml("");
      refreshLlms();
    } catch (e) {
      setImportMsg((e as Error).message);
    }
  }

  return (
    <div className="page settings">
      <h2>Provider accounts</h2>
      <div className="provider-logins"><ProviderLogin provider="openai" /><ProviderLogin provider="anthropic" /></div>
      <EnvironmentSettings />
      <header className="page-head">
        <div>
          <h1>Settings</h1>
          <p className="muted">
            LLM models the agents can use. Anything <a href="https://docs.litellm.ai/docs/providers" target="_blank" rel="noreferrer">LiteLLM supports</a> works.
            API keys are stored in the container's <code>/config</code> volume, not in <code>data/</code>, and are never shown again.
          </p>
        </div>
        {!form && (
          <button className="primary" onClick={() => setForm({ ...EMPTY })}>
            + Add model
          </button>
        )}
      </header>

      {form && (
        <form className="panel llm-form" onSubmit={save}>
          <h3>{form.id ? "Edit model" : "Add model"}</h3>
          <label><span>Model presets</span><select value="" onChange={e => {
            const preset = catalog.find(m => m.model === e.target.value);
            if (preset) {
              const router = preset.model.startsWith("openrouter/");
              set({ model: preset.model, model_name: preset.name, auth_mode: router ? "api_key" : "browser",
                api_key: router ? (provider === "openrouter" && form.api_key ? form.api_key : OPENROUTER_KEY) : "",
                api_base: "", api_version: "", extra: [], tools: "auto", vision: "auto" });
            }
          }}><option value="">Choose a model…</option>{catalog.map(m => <option key={m.model} value={m.model}>{m.name}</option>)}</select></label>
          {!form.id && (
            <div className="presets">
              {PRESETS.map((p) => (
                <button type="button" key={p.label} onClick={() => set({ ...EMPTY, ...p.form })}>
                  {p.label}
                </button>
              ))}
            </div>
          )}
          <label>
            <span>Model</span>
            <input
              required
              list="model-suggestions"
              placeholder="provider/model, e.g. anthropic/claude-sonnet-5"
              value={form.model}
              onChange={(e) => set({ model: e.target.value, ...(!["openai", "anthropic", "chatgpt"].includes(e.target.value.split("/")[0]) ? { auth_mode: "api_key" as const } : {}) })}
            />
            <datalist id="model-suggestions">
              {suggestions.slice(0, 300).map((m) => (
                <option key={m} value={m.includes("/") && m.startsWith(provider + "/") ? m : `${provider}/${m}`} />
              ))}
            </datalist>
            <small className="muted">
              The LiteLLM model string: <code>provider/model-name</code>.{" "}
              {provider && !providers.includes(provider) && providers.length > 0 && (
                <span className="warn-text">“{provider}” isn't a provider LiteLLM knows.</span>
              )}
            </small>
          </label>
          <label>
            <span>Display name</span>
            <input value={form.model_name} placeholder="Shown in the model picker" onChange={(e) => set({ model_name: e.target.value })} />
          </label>
          <label><span>Authentication</span><select value={form.auth_mode} onChange={e => set({ auth_mode: e.target.value as Form["auth_mode"] })}>
            {["openai", "anthropic", "chatgpt"].includes(provider) && <option value="browser">Browser login</option>}
            <option value="api_key">API key</option>
          </select></label>
          {form.auth_mode === "browser" && <p className="muted small">Uses the provider account connected above.</p>}
          {form.auth_mode === "api_key" && <>
          {provider === "openrouter" && <p className="muted small">
            Choose an OpenRouter model preset above, or enter <code>openrouter/vendor/model</code>.
            The environment key is selected by default; set it in Environment variables above or paste a key below.
            OpenRouter uses its own API key and billing. Leave the API base URL empty for the standard service.
          </p>}
          <label>
            <span>API key</span>
            <input
              type="password"
              autoComplete="off"
              value={form.api_key}
              placeholder={provider === "openrouter" ? "sk-or-…  or  " + OPENROUTER_KEY : "sk-…  or  os.environ/ANTHROPIC_API_KEY"}
              onChange={(e) => set({ api_key: e.target.value })}
            />
            <small className="muted">
              Leave the masked value to keep the stored key. <code>os.environ/NAME</code> uses the saved Environment variables above first,
              then the container's environment (e.g. a <code>.env</code> file next to docker-compose.yml).
            </small>
          </label>
          <div className="row">
            <label>
              <span>API base URL</span>
              <input value={form.api_base} placeholder="optional" onChange={(e) => set({ api_base: e.target.value })} />
            </label>
            <label>
              <span>API version</span>
              <input value={form.api_version} placeholder="optional (Azure)" onChange={(e) => set({ api_version: e.target.value })} />
            </label>
          </div>
          <fieldset>
            <legend>Extra LiteLLM parameters</legend>
            <small className="muted">
              Passed as-is to <code>litellm.completion()</code>, e.g. <code>temperature</code>, <code>max_tokens</code>,{" "}
              <code>aws_region_name</code>, <code>vertex_project</code>. JSON values are parsed.
            </small>
            {form.extra.map((row, i) => (
              <div className="row extra-row" key={i}>
                <input
                  placeholder="name"
                  value={row.key}
                  onChange={(e) => set({ extra: form.extra.map((r, j) => (j === i ? { ...r, key: e.target.value } : r)) })}
                />
                <input
                  placeholder="value"
                  value={row.value}
                  onChange={(e) => set({ extra: form.extra.map((r, j) => (j === i ? { ...r, value: e.target.value } : r)) })}
                />
                <button type="button" className="icon-button" aria-label="Remove" onClick={() => set({ extra: form.extra.filter((_, j) => j !== i) })}>
                  ✕
                </button>
              </div>
            ))}
            <button type="button" onClick={() => set({ extra: [...form.extra, { key: "", value: "" }] })}>
              + Parameter
            </button>
          </fieldset>
          </>}
          <div className="row">
            <label>
              <span>Tool calling</span>
              <select value={form.tools} onChange={(e) => set({ tools: e.target.value as CapChoice })}>
                <option value="auto">Auto (ask LiteLLM)</option>
                <option value="yes">Supported</option>
                <option value="no">Not supported (chat only)</option>
              </select>
            </label>
            <label>
              <span>Image input</span>
              <select value={form.vision} onChange={(e) => set({ vision: e.target.value as CapChoice })}>
                <option value="auto">Auto (ask LiteLLM)</option>
                <option value="yes">Supported — agent sees its renders</option>
                <option value="no">Not supported</option>
              </select>
            </label>
          </div>
          {error && <div className="banner error">{error}</div>}
          <div className="form-actions">
            <button type="button" onClick={() => setForm(null)}>
              Cancel
            </button>
            <button type="submit" className="primary">
              Save
            </button>
          </div>
        </form>
      )}

      <div className="llm-list">
        {llms.length === 0 && !form && <p className="muted">No models yet. Add one to start chatting.</p>}
        {llms.map((m) => {
          const t = tests[m.id];
          return (
            <div key={m.id} className="panel llm-row">
              <div className="llm-info">
                <div className="llm-title">
                  <strong>{m.model_name}</strong>
                  {m.id === defaultLlmId && <span className="badge">default</span>}
                  <span className="badge">{m.auth_mode === "browser" ? "browser login" : "API key"}</span>
                  <CapBadge label="tools" value={m.resolved_capabilities.tools} />
                  <CapBadge label="images" value={m.resolved_capabilities.vision} />
                </div>
                <div className="muted small">
                  <code>{String(m.litellm_params.model)}</code>
                  {m.litellm_params.api_base ? <> · {String(m.litellm_params.api_base)}</> : null}
                  {m.litellm_params.api_key ? <> · key {String(m.litellm_params.api_key)}</> : null}
                </div>
                {m.resolved_capabilities.tools === false && (
                  <div className="warn-text small">
                    LiteLLM reports no tool calling for this model: the agent won't be able to build or render. Set “Tool calling” to
                    Supported if you know better.
                  </div>
                )}
                {t && (
                  <div className={`small ${t === "running" ? "muted" : t.ok ? "ok-text" : "warn-text"}`}>
                    {t === "running" ? "Testing…" : t.text}
                  </div>
                )}
              </div>
              <div className="llm-actions">
                <button onClick={() => test(m.id)} disabled={t === "running"}>
                  Test
                </button>
                <button onClick={() => setForm(toForm(m))}>Edit</button>
                {m.id !== defaultLlmId && (
                  <button onClick={() => api.defaultLlm(m.id).then(refreshLlms)}>Make default</button>
                )}
                <button className="danger-text" onClick={() => remove(m)}>
                  Delete
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <details className="panel import">
        <summary>Import / export (LiteLLM <code>model_list</code> YAML)</summary>
        <p className="muted small">
          Paste a LiteLLM proxy config (or just its <code>model_list</code>). <a href="/api/llm-models/export">Export current models</a>{" "}
          (keys are masked in the export).
        </p>
        <textarea
          rows={8}
          value={yaml}
          placeholder={"model_list:\n  - model_name: Claude Sonnet 5\n    litellm_params:\n      model: anthropic/claude-sonnet-5\n      api_key: os.environ/ANTHROPIC_API_KEY"}
          onChange={(e) => setYaml(e.target.value)}
        />
        <div className="form-actions">
          {importMsg && <span className="small muted">{importMsg}</span>}
          <button onClick={importYaml} disabled={!yaml.trim()}>
            Import
          </button>
        </div>
      </details>
    </div>
  );
}
