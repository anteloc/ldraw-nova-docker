import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { viewerUrl, type ChatModel } from "../api";
import { useApp } from "../context";

/** Markdown with GitHub's extensions (tables, task lists, ...). Raw HTML is shown as text, never run. */
export default function Markdown({ children, models = [] }: { children: string; models?: ChatModel[] }) {
  const { openViewer } = useApp();
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: ({ href, children }) => {
        let model: ChatModel | undefined;
        try {
          const url = new URL(href ?? "", window.location.href);
          if (url.origin === window.location.origin && !url.searchParams.has("download")) {
            model = models.find(m => m.model_url && new URL(m.model_url, window.location.href).pathname === url.pathname);
          }
        } catch { /* ordinary Markdown link */ }
        if (!model?.model_url) return <a href={href}>{children}</a>;
        const target = { modelUrl: model.model_url, title: model.description || model.file, parts: model.parts };
        return <a href={viewerUrl(model.model_url, model.parts)} onClick={e => {
          if (e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) { e.preventDefault(); openViewer(target); }
        }}>{children}</a>;
      } }}>{children}</ReactMarkdown>
    </div>
  );
}
