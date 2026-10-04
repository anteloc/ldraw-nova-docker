import { type ChatModel, type Message, type ToolCall } from "../api";

type Status = "running" | "queued" | "done" | "interrupted";

const LABELS: Record<string, string> = {
  find_parts: "Searched parts",
  save_model: "Saved model",
  write_file: "Wrote file",
  render_model: "Rendered",
  run_python: "Ran Python",
  run_shell: "Ran shell",
  list_files: "Listed files",
  read_file: "Read file",
  run_toolkit: "LDraw Nova",
  publish_model: "Published model",
  submit_brick_design: "Voxel design",
  accept_design: "Finished sculpture",
  view_image: "Reviewed image",
  report_progress: "Progress",
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
    case "run_toolkit":
      return Array.isArray(args.arguments) ? args.arguments.join(" ") : "";
    case "report_progress":
      return pick("summary");
    case "run_python":
      return pick("code").split("\n").find((l) => l.trim() && !l.trim().startsWith("#"))?.trim() ?? "";
    case "run_shell":
      return pick("command");
    case "submit_brick_design":
      return pick("title");
    case "save_model":
      return pick("name");
    case "render_model":
    case "publish_model":
    case "view_image":
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
  live,
  now = Date.now(),
}: {
  call: ToolCall;
  result?: Message;
  status: Status;
  models: ChatModel[];
  live?: { output?: string; started_at?: number };
  now?: number;
}) {
  const name = call.function.name;
  const args = parseArgs(call.function.arguments);
  const output = typeof result?.content === "string" ? result.content : "";
  const failed = output.startsWith("Error:") || /^\[(?:timed out|exit code [1-9])/.test(output);
  const modelImages = new Set(models.map((m) => m.image_url));
  const extraImages = (result?._image_urls ?? []).filter((url) => !modelImages.has(url));

  return (
    <div className="tool">
      <details>
        <summary>
          <span className={`tool-status ${failed ? "failed" : status}`} aria-hidden />
          <span className="tool-name">{LABELS[name] ?? name}</span>
          <span className="tool-summary ellipsis">{summary(name, args)}</span>
          {status === "running" && <span className="muted small">{live?.started_at ? `${Math.max(0, Math.floor(now / 1000 - live.started_at))}s` : "running…"}</span>}
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
      {name === "report_progress" && <p className="progress-summary">{summary(name, args)}</p>}
      {status === "running" && live?.output && <pre className="live-tool-output">{live.output.slice(-4000)}</pre>}
      {extraImages.map((url) => (
        <a key={url} className="tool-image" href={url} target="_blank" rel="noreferrer">
          <img src={url} alt="render" loading="lazy" />
        </a>
      ))}
    </div>
  );
}
