import { NavLink, useMatch, useNavigate } from "react-router-dom";
import { api, timeAgo, type Chat } from "../api";
import { useApp } from "../context";

export default function Sidebar() {
  const { chats, chatsLoaded, refreshChats, openViewer } = useApp();
  const navigate = useNavigate();
  const current = useMatch("/chat/:id")?.params.id;

  async function remove(chat: Chat) {
    if (!confirm(`Delete "${chat.title}"?\n\nThis removes data/chats/${chat.id}/ and the agent's work folder data/output/${chat.id}/. Its models stay in data/generated.`)) return;
    await api.deleteChat(chat.id);
    refreshChats();
    if (current === chat.id) navigate("/");
  }

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark" aria-hidden />
        LDraw Astra
      </div>
      <NavLink className="button new-chat" to="/new">
        + New chat
      </NavLink>
      <nav className="nav">
        <NavLink to="/models">Models</NavLink>
        <NavLink to="/settings">Settings</NavLink>
      </nav>

      <div className="section-label">History</div>
      <div className="chat-list">
        {chatsLoaded && chats.length === 0 && <p className="muted small pad">No chats yet.</p>}
        {chats.map((chat) => {
          const shots = (chat.models ?? []).filter((m) => m.image_url && m.model_url).slice(-4).reverse();
          return (
            <div key={chat.id} className={`chat-item ${current === chat.id ? "active" : ""}`}>
              <NavLink to={`/chat/${chat.id}`} className="chat-link">
                <span className="chat-title">
                  {chat.running && <span className="live-dot" title="Working…" />}
                  {chat.title}
                </span>
                <span className="chat-time">{timeAgo(chat.updated_at)}</span>
              </NavLink>
              {shots.length > 0 && (
                <div className="chat-thumbs">
                  {shots.map((m) => (
                    <button
                      key={m.id}
                      className="chat-thumb"
                      title={`${m.name} — open in 3D`}
                      onClick={() => openViewer({ modelUrl: m.model_url!, title: m.description || m.name, parts: m.parts })}
                    >
                      <img src={m.image_url!} alt={m.name} loading="lazy" />
                    </button>
                  ))}
                </div>
              )}
              <button className="chat-delete" title="Delete chat" onClick={() => remove(chat)}>
                ×
              </button>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
