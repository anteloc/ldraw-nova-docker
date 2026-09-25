import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useParams } from "react-router-dom";
import { api, type Artifact, type ChatDetail, type Message } from "../api";
import Composer from "../components/Composer";
import ToolCard from "../components/ToolCard";
import { useApp } from "../context";

type RunningTool = { id: string; name: string; arguments: string };

const text = (m: Message) => (typeof m.content === "string" ? m.content : "");

function Markdown({ children }: { children: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}

export default function ChatPage() {
  const { id = "" } = useParams();
  const { llms, defaultLlmId, refreshChats } = useApp();
  const [detail, setDetail] = useState<ChatDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [running, setRunning] = useState(false);
  const [draft, setDraft] = useState("");
  const [persisting, setPersisting] = useState("");
  const [tools, setTools] = useState<RunningTool[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [llmId, setLlmId] = useState<string | null>(null);
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
    es.addEventListener("model", () => refreshChats());
    es.addEventListener("turn_error", (e) => setError(data(e).message));
    es.addEventListener("done", () => {
      es.close();
      setRunning(false);
      setTools([]);
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

  // Fall back to the default model when the chat's model was deleted.
  useEffect(() => {
    if (llms.length && (!llmId || !llms.some((m) => m.id === llmId))) setLlmId(defaultLlmId ?? llms[0].id);
  }, [llms, llmId, defaultLlmId]);

  useLayoutEffect(() => {
    if (stickToBottom.current) bottomRef.current?.scrollIntoView({ block: "end" });
  }, [detail, draft, persisting, tools]);

  function onScroll() {
    const el = scrollerRef.current;
    if (el) stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  async function send(value: string) {
    setError(null);
    stickToBottom.current = true;
    try {
      await api.send(id, value, llmId);
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
  const artifactsFor = (m?: Message): Artifact[] =>
    (m?._artifacts ?? []).map((a) => detail.artifacts[a]).filter(Boolean);
  const idle = running && !draft && !persisting && tools.length === 0;

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
                <div className="bubble">{text(m)}</div>
              </div>
            );
          }
          return (
            <div key={m.id} className="msg assistant">
              {text(m) && <Markdown>{text(m)}</Markdown>}
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
                  <ToolCard key={call.id} call={call} result={result} status={status} artifacts={artifactsFor(result)} />
                );
              })}
            </div>
          );
        })}
        {(persisting || draft) && (
          <div className="msg assistant">
            <Markdown>{persisting || draft}</Markdown>
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
        <Composer
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
