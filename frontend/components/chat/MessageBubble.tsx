import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { SourceChunk } from "@/lib/api";
import Icon from "@/components/Icon";
import SourceCitations from "./SourceCitations";

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: SourceChunk[];
  timestamp: string;
}

export default function MessageBubble({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="flex flex-col items-end gap-xs self-end max-w-[80%] ml-auto">
        <div className="bg-surface-container-highest text-on-surface px-sm py-xs rounded-lg rounded-tr-none border border-surface-variant">
          <p className="font-body-md text-body-md whitespace-pre-wrap">{message.text}</p>
        </div>
        <span className="font-label-sm text-label-sm font-mono text-on-surface-variant">
          {message.timestamp}
        </span>
      </div>
    );
  }

  return (
    <div className="flex gap-sm self-start max-w-[90%]">
      <div className="w-8 h-8 rounded-full bg-secondary-container flex items-center justify-center flex-shrink-0">
        <Icon name="smart_toy" className="text-on-secondary-container" size={16} />
      </div>
      <div className="flex flex-col gap-sm w-full">
        <div className="bg-surface-container-lowest text-on-surface p-sm rounded-xl border border-surface-variant shadow-sm flex flex-col gap-sm">
          <div className="chat-markdown font-body-md text-body-md">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown>
          </div>
          {message.sources && message.sources.length > 0 && (
            <SourceCitations sources={message.sources} />
          )}
        </div>
        <span className="font-label-sm text-label-sm font-mono text-on-surface-variant">
          {message.timestamp}
        </span>
      </div>
    </div>
  );
}
