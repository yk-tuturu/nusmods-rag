import type { SourceChunk } from "@/lib/api";
import SourceCitations from "./SourceCitations";

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: SourceChunk[];
}

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.text}</p>
        {!isUser && message.sources && <SourceCitations sources={message.sources} />}
      </div>
    </div>
  );
}
