import { useCallback, useEffect, useMemo, useState } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { api, type Chat, type LlmEntry } from "./api";
import { AppContext, type ViewerTarget } from "./context";
import Sidebar from "./components/Sidebar";
import ViewerModal from "./components/ViewerModal";
import ChatPage from "./pages/ChatPage";
import Gallery from "./pages/Gallery";
import Home from "./pages/Home";
import Outputs from "./pages/Outputs";
import Settings from "./pages/Settings";

export default function App() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [llms, setLlms] = useState<LlmEntry[]>([]);
  const [defaultLlmId, setDefaultLlmId] = useState<string | null>(null);
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  const refreshChats = useCallback(() => {
    api.chats().then((r) => setChats(r.chats)).catch(() => {});
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
    () => ({ chats, refreshChats, llms, defaultLlmId, refreshLlms, openViewer: setViewer }),
    [chats, refreshChats, llms, defaultLlmId, refreshLlms],
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
            <Route path="/" element={<Home />} />
            <Route path="/chat/:id" element={<ChatPage />} />
            <Route path="/gallery" element={<Gallery />} />
            <Route path="/outputs/*" element={<Outputs />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Home />} />
          </Routes>
        </main>
      </div>
      {viewer && <ViewerModal target={viewer} onClose={() => setViewer(null)} />}
    </AppContext.Provider>
  );
}
