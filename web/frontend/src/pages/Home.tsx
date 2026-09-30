import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type TurnOptions, type DocumentUpload } from "../api";
import Composer from "../components/Composer";
import { useApp } from "../context";

const EXAMPLES = [
  "Build a small red car with four black wheels",
  "A 6 x 8 cottage with a door, two windows and a sloped roof",
  "Build a spiral staircase around a tall stone tower",
  "Design a harbour crane with a long boom and a cargo dock",
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

  async function start(text: string, options: TurnOptions, images: string[], documents: DocumentUpload[]) {
    setError(null);
    try {
      const chat = await api.createChat(llmId);
      await api.send(chat.id, text, llmId, options, images, documents);
      refreshChats();
      navigate(`/chat/${chat.id}`);
    } catch (e) {
      setError((e as Error).message);
      throw e;
    }
  }

  return (
    <div className="page home">
      <div className="home-hero">
        <h1>What should we build?</h1>
        <p className="muted">
          Turn your ideas into LEGO models you can explore in 3D. Start building with an agent,
          or use Plan mode to work out your design.
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
