import type { LlmEntry } from "./api";

const RECENTS_KEY = "ldraw-astra.recent-models";
export function recentModels(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(RECENTS_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((id): id is string => typeof id === "string").slice(0, 5) : [];
  } catch { return []; }
}

export function rememberModel(id: string) {
  const ids = [id, ...recentModels().filter(previous => previous !== id)].slice(0, 5);
  try { localStorage.setItem(RECENTS_KEY, JSON.stringify(ids)); } catch { /* private browsing */ }
  return ids;
}

export function providerName(model: LlmEntry) {
  const provider = String(model.litellm_params.model).split("/")[0];
  if (provider === "openrouter") return "OpenRouter";
  if (provider === "chatgpt" || (provider === "openai" && model.auth_mode === "browser")) return "ChatGPT";
  return ({ openai: "OpenAI", anthropic: "Claude", gemini: "Gemini", vertex_ai: "Google Vertex AI",
    ollama_chat: "Ollama", ollama: "Ollama", azure: "Azure OpenAI" } as Record<string, string>)[provider] ?? provider;
}

export function tokenLabel(tokens: number) {
  if (tokens >= 1_000_000) return `${Number((tokens / 1_000_000).toFixed(2))}M`;
  if (tokens >= 1000) return `${Number((tokens / 1000).toFixed(2))}K`;
  return String(tokens);
}
