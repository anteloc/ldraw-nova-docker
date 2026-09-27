import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Markdown with GitHub's extensions (tables, task lists, ...). Raw HTML is shown as text, never run. */
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
