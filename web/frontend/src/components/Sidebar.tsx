import { NavLink, useMatch, useNavigate } from "react-router-dom";
import { api, fileUrl, timeAgo, type Chat } from "../api";
import { useApp } from "../context";

export default function Sidebar() {
  const { chats, refreshChats, openViewer } = useApp();
  const navigate = useNavigate();
  const current = useMatch("/chat/:id")?.params.id;

  async function remove(chat: Chat) {
    if (!confirm(`Delete "${chat.title}"?\n\nThe chat history is removed. Its models stay in data/generated/${chat.id}/.`)) return;
    await api.deleteChat(chat.id);
    refreshChats();
    if (current === chat.id) navigate("/");
  }

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark" aria-hidden />
        LeoCAD Agent
      </div>
      <button className="new-chat" onClick={() => navigate("/")}>
        + New chat
      </button>
      <nav className="nav">
        <NavLink to="/gallery">Models</NavLink>
        <NavLink to="/outputs">Outputs</NavLink>
        <NavLink to="/settings">Settings</NavLink>
      </nav>

      <div className="section-label">History</div>
      <div className="chat-list">
        {chats.length === 0 && <p className="muted small pad">No chats yet.</p>}
        {chats.map((chat) => {
          const shots = (chat.artifacts ?? []).filter((a) => a.image_path).slice(-4).reverse();
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
                  {shots.map((a) => (
                    <button
                      key={a.id}
                      className="chat-thumb"
                      title={`${a.name} — open in 3D`}
                      onClick={() => openViewer({ modelUrl: fileUrl(a.model_path), title: a.name })}
                    >
                      <img src={fileUrl(a.image_path!)} alt={a.name} loading="lazy" />
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
