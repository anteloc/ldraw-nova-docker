import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, type Chat, type LlmEntry } from "./api";
import { AppContext, type ViewerTarget } from "./context";
import Sidebar from "./components/Sidebar";
import ViewerModal from "./components/ViewerModal";
import ChatPage from "./pages/ChatPage";
import Home from "./pages/Home";
import Models from "./pages/Models";
import Settings from "./pages/Settings";

export default function App() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [chatsLoaded, setChatsLoaded] = useState(false);
  const [llms, setLlms] = useState<LlmEntry[]>([]);
  const [defaultLlmId, setDefaultLlmId] = useState<string | null>(null);
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  const refreshChats = useCallback(() => {
    api
      .chats()
      .then((r) => {
        setChats(r.chats);
        setChatsLoaded(true);
      })
      .catch(() => {});
  }, []);
  const refreshLlms = useCallback(() => {
    api
      .llmModels()
      .then((r) => {
        setLlms(r.models);
        setDefaultLlmId(r.default_id);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshChats();
    refreshLlms();
  }, [refreshChats, refreshLlms]);

  useEffect(() => setMenuOpen(false), [location.pathname]);

  const state = useMemo(
    () => ({ chats, chatsLoaded, refreshChats, llms, defaultLlmId, refreshLlms, openViewer: setViewer }),
    [chats, chatsLoaded, refreshChats, llms, defaultLlmId, refreshLlms],
  );

  return (
    <AppContext.Provider value={state}>
      <div className={`app ${menuOpen ? "menu-open" : ""}`}>
        <Sidebar />
        <div className="scrim" onClick={() => setMenuOpen(false)} />
        <main className="main">
          <button className="menu-button" aria-label="Open menu" onClick={() => setMenuOpen(true)}>
            ☰
          </button>
          <Routes>
            <Route path="/" element={<Navigate to="/models" replace />} />
            <Route path="/new" element={<Home />} />
            <Route path="/chat/:id" element={<ChatPage />} />
            <Route path="/models" element={<Models />} />
            <Route path="/gallery" element={<Navigate to="/models" replace />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/models" replace />} />
          </Routes>
        </main>
      </div>
      {viewer && <ViewerModal target={viewer} onClose={() => setViewer(null)} />}
    </AppContext.Provider>
  );
}
