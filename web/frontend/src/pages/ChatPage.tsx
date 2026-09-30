import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { api, isPending, type ChatDetail, type ChatModel, type Message, type Approval, type TurnOptions, type DocumentUpload } from "../api";
import Composer from "../components/Composer";
import Markdown from "../components/Markdown";
import ToolCard from "../components/ToolCard";
import ModelCard from "../components/ModelCard";
import { useApp } from "../context";
import { placeChatModels } from "../chatModels";
import DocumentIcon from "../components/DocumentIcon";

type RunningTool = { id: string; name: string; arguments: string; output?: string; started_at?: number };
type Activity = { started_at: number; last_event_at: number; phase: string };

type ContentBlock = { type: string; text?: string; image_url?: { url: string } };
const text = (m: Message) => typeof m.content === "string" ? m.content : Array.isArray(m.content) ? (m.content as ContentBlock[]).filter(b => b.type === "text").map(b => b.text).join("\n") : "";

export default function ChatPage() {
  const { id = "" } = useParams();
  const { hash } = useLocation();
  const anchored = useRef("");
  const { llms, defaultLlmId, refreshChats } = useApp();
  const [detail, setDetail] = useState<ChatDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [running, setRunning] = useState(false);
  const [draft, setDraft] = useState("");
  const [persisting, setPersisting] = useState("");
  const [tools, setTools] = useState<RunningTool[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [llmId, setLlmId] = useState<string | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [contextNotice, setContextNotice] = useState("");
  const [activity, setActivity] = useState<Activity | null>(null);
  const [connected, setConnected] = useState(true);
  const [now, setNow] = useState(Date.now());
  const draftRef = useRef("");
  const sourceRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  const reload = useCallback(async () => {
    const d = await api.chat(id);
    setDetail(d);
    return d;
  }, [id]);

  const updateDraft = (value: string) => {
    draftRef.current = value;
    setDraft(value);
  };

  // Live events for the running turn. The DB stays the source of truth: every
  // "saved" event triggers a refetch; the stream only carries in-flight text/tools.
  const subscribe = useCallback(() => {
    sourceRef.current?.close();
    const es = new EventSource(`/api/chats/${id}/stream`);
    sourceRef.current = es;
    setRunning(true);
    const data = (e: Event) => JSON.parse((e as MessageEvent).data);
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.addEventListener("reconnect", () => { es.close(); subscribe(); });

    es.addEventListener("snapshot", (e) => {
      const d = data(e);
      if (!d.running) {
        es.close();
        setRunning(false);
        reload();
        return;
      }
      updateDraft(d.draft);
      setTools(d.tools);
      setApprovals(d.approvals ?? []);
      setActivity(d.activity ?? null);
    });
    es.addEventListener("activity", e => setActivity(data(e)));
    es.addEventListener("progress", e => setActivity(a => ({
      started_at: a?.started_at ?? Date.now() / 1000,
      last_event_at: Date.now() / 1000, phase: data(e).summary,
    })));
    es.addEventListener("tool_output", e => {
      const d = data(e);
      setTools(all => all.map(t => t.id === d.id ? { ...t, output: ((t.output ?? "") + d.delta).slice(-12000) } : t));
    });
    es.addEventListener("text", (e) => updateDraft(draftRef.current + data(e).delta));
    es.addEventListener("tool_start", (e) => {
      const t = data(e) as RunningTool;
      setTools((all) => [...all.filter((x) => x.id !== t.id), t]);
    });
    es.addEventListener("tool_end", (e) => setTools((all) => all.filter((x) => x.id !== data(e).id)));
    es.addEventListener("saved", () => {
      // Keep showing the finished text until the refetch brings the saved message.
      setPersisting(draftRef.current);
      updateDraft("");
      reload().then(() => setPersisting(""));
    });
    es.addEventListener("model", () => { reload(); refreshChats(); });
    es.addEventListener("turn_error", (e) => setError(data(e).message));
    es.addEventListener("approval", e => setApprovals(all => [...all.filter(a => a.id !== data(e).id), data(e)]));
    es.addEventListener("approval_resolved", e => setApprovals(all => all.filter(a => a.id !== data(e).id)));
    es.addEventListener("context", () => setContextNotice("Earlier conversation or completed tool steps were omitted to fit the context budget. Saved history and build files are unchanged."));
    es.addEventListener("done", () => {
      es.close();
      setRunning(false);
      setTools([]);
      setApprovals([]);
      updateDraft("");
      reload();
      refreshChats();
    });
  }, [id, reload, refreshChats]);

  useEffect(() => {
    setDetail(null);
    setNotFound(false);
    setError(null);
    setTools([]);
    setApprovals([]);
    setContextNotice("");
    setActivity(null);
    setConnected(true);
    updateDraft("");
    setPersisting("");
    stickToBottom.current = true;
    reload()
      .then((d) => {
        setLlmId(d.chat.llm_model_id);
        if (d.chat.running) subscribe();
        else setRunning(false);
      })
      .catch(() => setNotFound(true));
    return () => sourceRef.current?.close();
  }, [id, reload, subscribe]);

  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running]);

  // Snapshots/BOMs of this chat's models still being made (e.g. a deleted .png): refetch until done.
  const snapshotsPending = !running && !!detail && Object.values(detail.models).some(isPending);
  useEffect(() => {
    if (!snapshotsPending) return;
    const timer = setTimeout(() => reload().then(() => refreshChats()), 1500);
    return () => clearTimeout(timer);
  }, [snapshotsPending, detail, reload, refreshChats]);

  // Fall back to the default model when the chat's model was deleted.
  useEffect(() => {
    if (llms.length && (!llmId || !llms.some((m) => m.id === llmId))) setLlmId(defaultLlmId ?? llms[0].id);
  }, [llms, llmId, defaultLlmId]);

  useLayoutEffect(() => {
    if (stickToBottom.current) bottomRef.current?.scrollIntoView({ block: "end" });
  }, [detail, draft, persisting, tools]);

  useEffect(() => {
    if (!hash.startsWith("#model-") || anchored.current === id + hash) return;
    const card = document.getElementById(hash.slice(1));
    if (card) {
      stickToBottom.current = false;
      card.scrollIntoView({ block: "center" });
      anchored.current = id + hash;
    }
  }, [id, hash, detail]);

  function onScroll() {
    const el = scrollerRef.current;
    if (el) stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  async function send(value: string, options: TurnOptions, images: string[], documents: DocumentUpload[]) {
    setError(null);
    stickToBottom.current = true;
    try {
      await api.send(id, value, llmId, options, images, documents);
    } catch (e) {
      setError((e as Error).message);
      throw e;
    }
    await reload();
    subscribe();
    refreshChats();
  }

  if (notFound) return <div className="page"><p className="muted">This chat doesn't exist (any more).</p></div>;
  if (!detail) return <div className="page"><p className="muted">Loading…</p></div>;

  const messages = detail.messages;
  const results = new Map(messages.filter((m) => m.role === "tool").map((m) => [m.tool_call_id, m]));
  const runningIds = new Set(tools.map((t) => t.id));
  const modelsFor = (m?: Message): ChatModel[] => (m?._models ?? []).map((id) => detail.models[id]).filter(Boolean);
  const idle = running && !draft && !persisting && tools.length === 0;
  const cards = placeChatModels(messages, detail.models);
  const publishedModels = Object.values(detail.models);
  const modelCard = (m: ChatModel) => <div id={`model-${m.id}`} className="chat-model" key={m.id}><ModelCard model={m} /></div>;
  const elapsed = activity ? Math.max(0, Math.floor(now / 1000 - activity.started_at)) : 0;

  return (
    <div className="chat-page">
      <header className="chat-head">
        <h2 className="ellipsis">{detail.chat.title}</h2>
      </header>
      <div className="messages" ref={scrollerRef} onScroll={onScroll}>
        {messages.map((m) => {
          if (m._hidden || m.role === "tool" || m.role === "system") return null;
          if (m._ui_only) {
            return (
              <div key={m.id} className={`banner ${m._error ? "error" : ""}`}>
                {text(m)}
              </div>
            );
          }
          if (m.role === "user") {
            return (
              <div key={m.id} className="msg user">
                <div className="bubble">{text(m)}
                  {Array.isArray(m.content) && <div className="attachments">{(m.content as ContentBlock[]).filter(b => b.type === "image_url").map((b, i) => <img key={i} src={b.image_url?.url} alt={`Attached image ${i + 1}`} />)}</div>}
                  {!!m._documents?.length && <div className="document-attachments">{m._documents.map((d, i) =>
                    <a className="document-chip" key={i} href={d.url ?? undefined} download={d.name}><DocumentIcon /><span>{d.name}</span></a>
                  )}</div>}
                </div>
              </div>
            );
          }
          return (
            <div key={m.id} className="msg assistant">
              {text(m) && <Markdown models={publishedModels}>{text(m)}</Markdown>}
              {(m.tool_calls ?? []).map((call) => {
                const result = results.get(call.id);
                const status = result
                  ? "done"
                  : runningIds.has(call.id)
                    ? "running"
                    : running
                      ? "queued"
                      : "interrupted";
                return (
                  <ToolCard key={call.id} call={call} result={result} status={status} models={modelsFor(result)}
                    live={tools.find(t => t.id === call.id)} now={now} />
                );
              })}
              {(cards.byMessage.get(m.id) ?? []).map(modelCard)}
            </div>
          );
        })}
        {cards.unplaced.map(m => (
          <div className="msg assistant" key={m.id}>{modelCard(m)}</div>
        ))}
        {(persisting || draft) && (
          <div className="msg assistant">
            <Markdown models={publishedModels}>{persisting || draft}</Markdown>
          </div>
        )}
        {idle && (
          <div className="msg assistant">
            <span className="thinking" aria-label="Thinking">
              <i />
              <i />
              <i />
            </span>
          </div>
        )}
        {error && !messages.some((m) => m._error && text(m) === error) && <div className="banner error">{error}</div>}
        <div ref={bottomRef} />
      </div>
      <div className="composer-wrap">
        {running && <div className="build-activity" role="status" aria-live="polite">
          <span className="spinner" aria-hidden />
          <span>{!connected ? "Reconnecting to live updates… Your build continues on the server." :
            approvals.length ? "Waiting for your approval" : activity?.phase || "Agent is working…"}</span>
          <time>{Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}</time>
        </div>}
        {contextNotice && <p className="muted small">{contextNotice}</p>}
        {approvals.map(a => <div className="panel approval" key={a.id}>
          <strong>Allow {a.name}?</strong><pre>{a.arguments}</pre>
          <button type="button" onClick={() => api.approve(id, a.id, false).catch(e => setError(e.message))}>Deny</button>{" "}
          <button type="button" className="primary" onClick={() => api.approve(id, a.id, true).catch(e => setError(e.message))}>Allow once</button>
        </div>)}
        <Composer
          key={id}
          initialOptions={detail.chat.options}
          llmId={llmId}
          onLlmChange={setLlmId}
          onSend={send}
          onStop={() => api.cancel(id)}
          running={running}
        />
      </div>
    </div>
  );
}
