import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type EnvironmentVariable } from "../api";

type Row = { key: string; id?: string; name: string; value: string | null; has_value: boolean };
const toRows = (variables: EnvironmentVariable[]): Row[] => variables.map(v => ({ ...v, key: v.id }));

export default function EnvironmentSettings() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const nextKey = useRef(0);

  useEffect(() => {
    let active = true;
    api.environment().then(result => {
      if (active) { setRows(toRows(result.variables)); setLoaded(true); }
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);

  function change(key: string, patch: Partial<Row>) {
    setRows(current => current.map(row => row.key === key ? { ...row, ...patch } : row));
    setDirty(true); setMessage(""); setError("");
  }

  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const result = await api.saveEnvironment(rows.map(({ id, name, value }) => ({ id, name: name.trim(), value })));
      setRows(toRows(result.variables)); setDirty(false);
      setMessage("Environment variables saved. New requests use these values.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  return <section className="panel environment-settings" aria-labelledby="environment-heading">
    <div className="environment-heading">
      <h2 id="environment-heading">Environment variables</h2>
      <button type="button" disabled={!loaded || busy} onClick={() => {
        const key = `new-${nextKey.current++}`;
        setRows(current => [...current, { key, name: "", value: "", has_value: false }]);
        setDirty(true); setMessage(""); setError("");
      }}>Add</button>
    </div>
    <p className="muted small">Saved values override inherited values. Choose “API key (env var)” in a model’s settings to use one. Changes apply after saving.</p>
    <form onSubmit={save}>
      <div className="environment-rows">
        {rows.map((row, index) => <div className="environment-row" key={row.key}>
          <label>
            <span>Name</span>
            <input aria-label={`Variable name ${index + 1}`} required pattern="[A-Za-z_][A-Za-z0-9_]*" maxLength={255}
              autoComplete="off" spellCheck={false} placeholder="OPENROUTER_API_KEY" disabled={busy}
              value={row.name} onChange={e => change(row.key, { name: e.target.value })} />
          </label>
          <label>
            <span>Value</span>
            <input aria-label={`Variable value ${index + 1}`} type="text" autoComplete="off" spellCheck={false} maxLength={65536}
              placeholder="Value (may be empty)" disabled={busy}
              value={row.value ?? ""}
              onChange={e => change(row.key, { value: e.target.value })} />
          </label>
          <button type="button" className="danger-text" aria-label={`Remove variable ${index + 1}`} disabled={busy} onClick={() => {
            setRows(current => current.filter(r => r.key !== row.key)); setDirty(true); setMessage(""); setError("");
          }}>Remove</button>
        </div>)}
      </div>
      {loaded && !rows.length && <p className="muted small">No environment overrides configured.</p>}
      {!loaded && !error && <p className="muted small">Loading environment variables…</p>}
      {rows.length > 0 && <p className="muted small">Removing a row restores the inherited value, if one exists.</p>}
      {error && <p className="warn-text" role="alert">{error}</p>}
      {message && <p className="ok-text small" role="status">{message}</p>}
      <div className="form-actions">
        {dirty && <span className="muted small">Unsaved changes</span>}
        <button type="submit" className="primary" disabled={!loaded || !dirty || busy}>{busy ? "Saving…" : "Save environment variables"}</button>
      </div>
    </form>
  </section>;
}
