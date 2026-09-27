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
    <div className="llm-title"><strong>{name}</strong><span className={`badge ${state.status === "connected" ? "ok" : ""}`}>{state.status}</span></div>
    <p className="muted small">{provider === "openai" ? "Sign in to ChatGPT in your browser, then return here. No device code or terminal command is needed." : "Sign in to Claude in your browser, then copy Claude's authorization code into this page to connect your account."} Model access depends on your account.</p>
    {state.status !== "connected" && !pending && <button type="button" className="primary" disabled={busy} onClick={() => login()}>Sign in with {name}</button>}
    {(pending || state.status === "connected") && <button type="button" disabled={busy} onClick={logout}>{pending ? "Cancel login" : "Disconnect"}</button>}
    {state.url && pending && <p><a href={state.url} target="_blank" rel="noreferrer">Open {name} sign-in</a></p>}
    {state.code && pending && state.flow === "device" && <p>After signing in, enter this code on OpenAI's device page: <strong className="device-code">{state.code}</strong></p>}
    {pending && provider === "openai" && state.flow !== "device" && <p className="muted small">Complete sign-in on the same computer that runs Docker. The browser returns automatically through localhost:1455.</p>}
    {provider === "openai" && state.status !== "connected" && <details className="small" style={{ marginTop: 12 }}>
      <summary>Signing in from another computer?</summary>
      <p>Use device sign-in when the browser is on a different computer from Docker. First enable <strong>device code sign-in</strong> in <a href="https://chatgpt.com/#settings/Security" target="_blank" rel="noreferrer">ChatGPT Security Settings</a>. Then start a fresh device login here.</p>
      <p>If OpenAI mentions a terminal command, use this button instead. The app runs the login and shows the code for you.</p>
      <button type="button" disabled={busy} onClick={() => login("device")}>Start device sign-in</button>
    </details>}
    {state.status === "pending" && provider === "anthropic" && <form onSubmit={async e => {
      e.preventDefault(); setError(""); setBusy(true);
      try { await api.loginCode(provider, code); setCode(""); }
      catch (e) { setError((e as Error).message); }
      finally { setBusy(false); }
    }}>
      <p className="muted small">Finish sign-in in the Claude tab, copy the full code it displays, then paste it below. You do not need a terminal.</p>
      <label><span>Claude authorization code</span><input type="password" autoComplete="off" spellCheck={false} value={code} onChange={e => setCode(e.target.value)} /></label>
      <button type="submit" disabled={!code.trim() || busy}>Complete login</button>
    </form>}
    {pending && <p className="muted small">Waiting for browser authentication. This page updates automatically.</p>}
    {(error || state.message) && <p role="alert" className="warn-text">{error || state.message}</p>}
  </section>;
}
