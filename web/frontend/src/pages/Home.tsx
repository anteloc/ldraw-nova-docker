import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import Composer from "../components/Composer";
import { useApp } from "../context";

const EXAMPLES = [
  "Build a small red car with four black wheels",
  "A 6 x 8 cottage with a door, two windows and a sloped roof",
  "Generate a spiral staircase with a Python script",
  "Which parts would make a crane's hook and boom? Show me the part ids",
];

export default function Home() {
  const { llms, defaultLlmId, refreshChats } = useApp();
  const navigate = useNavigate();
  const [llmId, setLlmId] = useState<string | null>(defaultLlmId);
  const [example, setExample] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!llmId || !llms.some((m) => m.id === llmId)) setLlmId(defaultLlmId ?? llms[0]?.id ?? null);
  }, [llms, defaultLlmId, llmId]);

  async function start(text: string) {
    setError(null);
    try {
      const chat = await api.createChat(llmId);
      await api.send(chat.id, text, llmId);
      refreshChats();
      navigate(`/chat/${chat.id}`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="page home">
      <div className="home-hero">
        <h1>What should we build?</h1>
        <p className="muted">
          Agents design LDraw models, render them with LeoCAD and show you the result. Click any screenshot to explore it
          in 3D. Everything is saved under <code>data/</code>.
        </p>
      </div>
      <div className="examples">
        {EXAMPLES.map((ex) => (
          <button key={ex} className="example" onClick={() => setExample(ex)}>
            {ex}
          </button>
        ))}
      </div>
      {error && <div className="banner error">{error}</div>}
      <Composer
        llmId={llmId}
        onLlmChange={setLlmId}
        onSend={start}
        running={false}
        autoFocus
        initialText={example}
      />
    </div>
  );
}
