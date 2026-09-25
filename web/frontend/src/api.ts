// Typed client for the FastAPI backend (web/backend/main.py).

export type Artifact = {
  id: string;
  chat_id: string;
  name: string;
  model_path: string; // relative to /data
  image_path: string | null; // relative to /data; null if the render failed
  warnings: string[];
  created_at: number;
  chat_title?: string;
};

export type Chat = {
  id: string;
  title: string;
  llm_model_id: string | null;
  created_at: number;
  updated_at: number;
  running?: boolean;
  artifacts?: Artifact[];
};

export type ToolCall = { id: string; type: "function"; function: { name: string; arguments: string } };

export type Message = {
  id: number;
  created_at: number;
  role: "user" | "assistant" | "tool" | "system";
  content: string | null | unknown[];
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  name?: string;
  _artifacts?: string[];
  _images?: string[];
  _hidden?: boolean;
  _ui_only?: boolean;
  _error?: boolean;
  _notice?: boolean;
  _reasoning?: string;
};

export type ChatDetail = { chat: Chat; messages: Message[]; artifacts: Record<string, Artifact> };

export type Capability = boolean | "auto";
export type LlmEntry = {
  id: string;
  model_name: string;
  litellm_params: Record<string, unknown>;
  capabilities: { tools: Capability; vision: Capability };
  resolved_capabilities: { tools: boolean | null; vision: boolean | null };
};

export type OutputListing = {
  dir: string;
  dirs: { name: string; path: string }[];
  files: {
    name: string;
    path: string;
    size: number;
    mtime: number;
    url: string;
    is_image: boolean;
    source: { url: string; name: string } | null;
  }[];
};

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  const type = res.headers.get("content-type") || "";
  return (type.includes("json") ? res.json() : res.text()) as Promise<T>;
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  chats: () => request<{ chats: Chat[] }>("/api/chats"),
  createChat: (llm_model_id?: string | null) =>
    request<Chat>("/api/chats", { method: "POST", body: json({ llm_model_id }) }),
  chat: (id: string) => request<ChatDetail>(`/api/chats/${id}`),
  renameChat: (id: string, title: string) =>
    request<Chat>(`/api/chats/${id}`, { method: "PATCH", body: json({ title }) }),
  deleteChat: (id: string, deleteFiles = false) =>
    request(`/api/chats/${id}?delete_files=${deleteFiles}`, { method: "DELETE" }),
  send: (id: string, text: string, llm_model_id?: string | null) =>
    request(`/api/chats/${id}/messages`, { method: "POST", body: json({ text, llm_model_id }) }),
  cancel: (id: string) => request(`/api/chats/${id}/cancel`, { method: "POST" }),
  artifacts: () => request<{ artifacts: Artifact[] }>("/api/artifacts"),
  outputs: (dir: string) => request<OutputListing>(`/api/outputs?dir=${encodeURIComponent(dir)}`),

  llmModels: () => request<{ models: LlmEntry[]; default_id: string | null }>("/api/llm-models"),
  createLlm: (entry: Partial<LlmEntry>) => request<LlmEntry>("/api/llm-models", { method: "POST", body: json(entry) }),
  updateLlm: (id: string, entry: Partial<LlmEntry>) =>
    request<LlmEntry>(`/api/llm-models/${id}`, { method: "PUT", body: json(entry) }),
  deleteLlm: (id: string) => request(`/api/llm-models/${id}`, { method: "DELETE" }),
  defaultLlm: (id: string) => request(`/api/llm-models/${id}/default`, { method: "POST" }),
  testLlm: (id: string) =>
    request<{ ok: boolean; reply?: string; error?: string; capabilities?: LlmEntry["resolved_capabilities"] }>(
      `/api/llm-models/${id}/test`,
      { method: "POST" },
    ),
  importLlm: (yaml: string) =>
    request<{ imported: LlmEntry[] }>("/api/llm-models/import", { method: "POST", body: json({ yaml }) }),
  providers: () => request<{ providers: string[] }>("/api/llm-providers"),
  providerModels: (p: string) => request<{ models: string[] }>(`/api/llm-providers/${encodeURIComponent(p)}/models`),
};

/** URL of a file under /data (paths from the API are relative to /data). */
export const fileUrl = (rel: string, download = false) =>
  "/files/" + rel.split("/").map(encodeURIComponent).join("/") + (download ? "?download=1" : "");

export const viewerUrl = (modelUrl: string) => `/viewer/viewer.html?model=${encodeURIComponent(modelUrl)}`;

export function timeAgo(seconds: number): string {
  const diff = Date.now() / 1000 - seconds;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} d ago`;
  return new Date(seconds * 1000).toLocaleDateString();
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
