"use client";

import { useEffect, useRef, useState } from "react";
import { sendChat, getCourses, type CourseSummary } from "@/lib/api";
import MessageBubble, { type Message } from "./MessageBubble";

let nextId = 0;
function makeId() {
  nextId += 1;
  return `msg-${nextId}`;
}

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [courses, setCourses] = useState<CourseSummary[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getCourses()
      .then(setCourses)
      .catch(() => setCourses([]));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { id: makeId(), role: "user", text: question }]);
    setLoading(true);

    try {
      const result = await sendChat(question, selectedCourse || undefined);
      setMessages((prev) => [
        ...prev,
        { id: makeId(), role: "assistant", text: result.answer, sources: result.sources },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col flex-1 w-full max-w-3xl mx-auto p-4 gap-4">
      <div className="flex items-center gap-2">
        <label htmlFor="course-picker" className="text-sm text-zinc-500">
          Scope to course:
        </label>
        <select
          id="course-picker"
          value={selectedCourse}
          onChange={(e) => setSelectedCourse(e.target.value)}
          className="text-sm rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-2 py-1"
        >
          <option value="">All courses</option>
          {courses.map((c) => (
            <option key={c.code} value={c.code}>
              {c.code}
              {c.title ? ` — ${c.title}` : ""}
            </option>
          ))}
        </select>
      </div>

      <div className="flex-1 overflow-y-auto flex flex-col gap-3 min-h-[300px]">
        {messages.length === 0 && (
          <p className="text-zinc-400 text-sm">
            Ask about workload, difficulty, prereqs, or professors for an NUS course.
          </p>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl px-4 py-2 bg-zinc-100 dark:bg-zinc-800 text-zinc-500">
              Thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && (
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Is CS2030 hard for beginners?"
          className="flex-1 rounded-full border border-zinc-300 dark:border-zinc-700 bg-transparent px-4 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-full bg-blue-600 text-white px-5 py-2 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
