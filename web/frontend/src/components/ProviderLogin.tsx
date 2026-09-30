import { useEffect, useRef, useState } from "react";
import { api, type AuthStatus } from "../api";

export default function ProviderLogin({ provider }: { provider: "openai" | "anthropic" }) {
  const [state, setState] = useState<AuthStatus>({ status: "disconnected" });
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const popup = useRef<Window | null>(null);
  const opened = useRef("");
  const pending = state.status === "starting" || state.status === "pending";
  const name = provider === "openai" ? "ChatGPT" : "Claude";
  const remote = !["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
  const device = provider === "openai" && (pending ? state.flow === "device" : remote);
  const statusText = { disconnected: "Not connected", connected: "Connected", starting: "Opening sign-in…", pending: "Waiting for sign-in", error: "Sign-in failed", expired: "Sign-in expired" }[state.status];

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await api.authStatus(provider);
        if (!active) return;
        setState(next);
        if (next.url && opened.current !== next.url && popup.current && !popup.current.closed) {
          popup.current.location.href = next.url;
          opened.current = next.url;
        }
      } catch (e) { if (active) setError((e as Error).message); }
      if (active) timer = setTimeout(poll, 2000);
    }
    poll();
    return () => { active = false; clearTimeout(timer); };
  }, [provider]);

  async function login(flow: "browser" | "device" = "browser") {
    // Open during the click so popup blockers don't discard the async login URL.
    popup.current = window.open("about:blank", "_blank");
    if (popup.current) { popup.current.opener = null; popup.current.document.title = `Connecting to ${name}…`; }
    opened.current = "";
    setBusy(true); setError(""); setCode("");
    try { setState(await api.login(provider, flow)); }
    catch (e) { popup.current?.close(); setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function logout() {
    setBusy(true); setError("");
    try { await api.logout(provider); setState({ status: "disconnected" }); setCode(""); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  return <section className="panel provider-login">
    <div className="llm-title"><strong>{name}</strong><span className={`badge ${state.status === "connected" ? "ok" : ""}`}>{statusText}</span></div>
    {state.status !== "connected" ? <ol className="login-steps muted small">
      {device && <li>Enable <strong>device code sign-in</strong> in <a href="https://chatgpt.com/#settings/Security" target="_blank" rel="noreferrer">ChatGPT Security Settings</a>.</li>}
      <li>Click <strong>Sign in with {name}</strong> and sign in on the page that opens.</li>
      {provider === "anthropic" ? <li>Copy the code Claude gives you, paste it below, and click <strong>Complete login</strong>.</li>
        : device ? <li>Enter the code shown here on the ChatGPT sign-in page.</li> : <li>Finish sign-in and return to this page.</li>}
      <li>Wait for <strong>Connected</strong>, then select <strong>Browser login</strong> when adding an agent from this provider below.</li>
    </ol> : <p className="muted small">Ready to use with agents set to Browser login. Available models depend on this account’s plan.</p>}
    {state.status !== "connected" && !pending && <button type="button" className="primary" disabled={busy} onClick={() => login(device ? "device" : "browser")}>Sign in with {name}</button>}
    {(pending || state.status === "connected") && <button type="button" disabled={busy} onClick={logout}>{pending ? "Cancel login" : "Disconnect"}</button>}
    {state.url && pending && <p><a href={state.url} target="_blank" rel="noreferrer">Open {name} sign-in</a></p>}
    {state.code && pending && state.flow === "device" && <p>After signing in, enter this code on OpenAI's device page: <strong className="device-code">{state.code}</strong></p>}
    {provider === "openai" && state.status !== "connected" && !device && <details className="small login-help">
      <summary>Sign-in doesn’t return here?</summary>
      <ol className="login-steps"><li>Enable <strong>device code sign-in</strong> in <a href="https://chatgpt.com/#settings/Security" target="_blank" rel="noreferrer">ChatGPT Security Settings</a>.</li>
        <li>Click <strong>Start device sign-in</strong> below.</li><li>Sign in, then enter the code shown here on the ChatGPT page.</li></ol>
      <p>If ChatGPT asks you to run a command, click this button to start again.</p>
      <button type="button" disabled={busy} onClick={() => login("device")}>Start device sign-in</button>
    </details>}
    {state.status === "pending" && provider === "anthropic" && <form onSubmit={async e => {
      e.preventDefault(); setError(""); setBusy(true);
      try { await api.loginCode(provider, code); setCode(""); }
      catch (e) { setError((e as Error).message); }
      finally { setBusy(false); }
    }}>
      <label><span>Claude sign-in code</span><input type="password" placeholder="Paste the full code from Claude" autoComplete="off" spellCheck={false} value={code} onChange={e => setCode(e.target.value)} /></label>
      <button type="submit" disabled={!code.trim() || busy}>Complete login</button>
    </form>}
    {pending && <p className="muted small">This page updates when sign-in is complete.</p>}
    {(error || state.message) && <p role="alert" className="warn-text">{error || state.message}</p>}
  </section>;
}
