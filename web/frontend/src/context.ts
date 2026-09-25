import { createContext, useContext } from "react";
import type { Chat, LlmEntry } from "./api";

export type ViewerTarget = { modelUrl: string; title: string };

export type AppState = {
  chats: Chat[];
  refreshChats: () => void;
  llms: LlmEntry[];
  defaultLlmId: string | null;
  refreshLlms: () => void;
  openViewer: (target: ViewerTarget) => void;
};

export const AppContext = createContext<AppState | null>(null);

export function useApp(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp outside <AppContext.Provider>");
  return ctx;
}
