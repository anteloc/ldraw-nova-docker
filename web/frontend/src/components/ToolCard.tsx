import { type ChatModel, type Message, type ToolCall } from "../api";
import ModelCard from "./ModelCard";

type Status = "running" | "queued" | "done" | "interrupted";

const LABELS: Record<string, string> = {
  find_parts: "Searched parts",
  search_reference_models: "Searched reference models",
  read_reference_model: "Read reference model",
  save_model: "Saved model",
  write_file: "Wrote file",
  render_model: "Rendered",
  run_python: "Ran Python",
  run_shell: "Ran shell",
  list_files: "Listed files",
  read_file: "Read file",
};

function parseArgs(raw: string): Record<string, unknown> {
  try {
    return JSON.parse(raw || "{}");
  } catch {
    return { raw };
  }
}

function summary(name: string, args: Record<string, unknown>): string {
  const pick = (k: string) => (typeof args[k] === "string" ? (args[k] as string) : "");
  switch (name) {
    case "run_python":
      return pick("code").split("\n").find((l) => l.trim() && !l.trim().startsWith("#"))?.trim() ?? "";
    case "run_shell":
      return pick("command");
    case "save_model":
      return pick("name");
    case "read_reference_model":
      return [pick("file"), pick("submodel")].filter(Boolean).join(" › ");
    case "render_model":
    case "read_file":
    case "write_file":
    case "list_files":
      return pick("path");
    default:
      return pick("query");
  }
}

function prettyArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([k, v]) => {
      const text = typeof v === "string" ? v : JSON.stringify(v);
      return text.includes("\n") ? `${k}:\n${text}` : `${k}: ${text}`;
    })
    .join("\n");
}

export default function ToolCard({
  call,
  result,
  status,
  models,
}: {
  call: ToolCall;
  result?: Message;
  status: Status;
  models: ChatModel[];
}) {
  const name = call.function.name;
  const args = parseArgs(call.function.arguments);
  const output = typeof result?.content === "string" ? result.content : "";
  const failed = output.startsWith("Error:");
  const modelImages = new Set(models.map((m) => m.image_url));
  const extraImages = (result?._image_urls ?? []).filter((url) => !modelImages.has(url));

  return (
    <div className="tool">
      <details>
        <summary>
          <span className={`tool-status ${failed ? "failed" : status}`} aria-hidden />
          <span className="tool-name">{LABELS[name] ?? name}</span>
          <span className="tool-summary ellipsis">{summary(name, args)}</span>
          {status === "running" && <span className="muted small">running…</span>}
          {status === "interrupted" && <span className="muted small">interrupted</span>}
        </summary>
        <div className="tool-body">
          <div className="tool-section">Arguments</div>
          <pre>{prettyArgs(args)}</pre>
          {result && (
            <>
              <div className="tool-section">Result</div>
              <pre className={failed ? "failed" : ""}>{output}</pre>
            </>
          )}
        </div>
      </details>
      {models.map((m) => (
        <ModelCard key={m.id} model={m} />
      ))}
      {extraImages.map((url) => (
        <a key={url} className="tool-image" href={url} target="_blank" rel="noreferrer">
          <img src={url} alt="render" loading="lazy" />
        </a>
      ))}
    </div>
  );
}
