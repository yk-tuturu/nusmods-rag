"use client";

import { useEffect, useRef, useState } from "react";
import { sendChat, getCourses, type CourseSummary, type SourceChunk } from "@/lib/api";
import Icon from "@/components/Icon";
import MessageBubble, { type Message } from "./MessageBubble";

const SUGGESTIONS = ["Compare CS2030S vs CS2040S", "Gen Ed requirements", "Is CS2103T heavy?"];

let nextId = 0;
function makeId() {
  nextId += 1;
  return `msg-${nextId}`;
}

function timestamp() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function ChatInterface() {
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
  }, [messages, loading]);

  const lastAssistantMessage = [...messages].reverse().find((m) => m.role === "assistant");
  const contextSources: SourceChunk[] = lastAssistantMessage?.sources ?? [];
  const contextCourseCodes = Array.from(
    new Set(contextSources.map((s) => s.course_code).filter(Boolean))
  ) as string[];

  async function submitQuestion(question: string) {
    if (!question || loading) return;

    setInput("");
    setError(null);
    setMessages((prev) => [
      ...prev,
      { id: makeId(), role: "user", text: question, timestamp: timestamp() },
    ]);
    setLoading(true);

    try {
      const result = await sendChat(question, selectedCourse || undefined);
      setMessages((prev) => [
        ...prev,
        {
          id: makeId(),
          role: "assistant",
          text: result.answer,
          sources: result.sources,
          timestamp: timestamp(),
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    submitQuestion(input.trim());
  }

  return (
    <>
      <main className="flex-1 flex flex-col h-full min-h-0 lg:ml-64 xl:mr-80 min-w-0">
        <div className="flex-1 min-h-0 overflow-y-auto chat-scrollbar p-gutter md:p-md flex flex-col gap-lg max-w-[900px] mx-auto w-full">
          <div className="flex flex-wrap items-center justify-between gap-xs -mt-1">
            <span className="font-label-sm text-label-sm font-mono text-on-surface-variant bg-surface-container rounded-full px-3 py-1">
              Today
            </span>
            <label className="flex items-center gap-xs font-label-sm text-label-sm font-mono text-on-surface-variant">
              Scope:
              <select
                value={selectedCourse}
                onChange={(e) => setSelectedCourse(e.target.value)}
                className="rounded-full border border-surface-variant bg-surface-container-lowest px-2 py-1 text-on-surface font-body-sm text-body-sm"
              >
                <option value="">All courses</option>
                {courses.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.code}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {messages.length === 0 && (
            <div className="flex gap-sm self-start max-w-[90%]">
              <div className="w-8 h-8 rounded-full bg-secondary-container flex items-center justify-center flex-shrink-0">
                <Icon name="smart_toy" className="text-on-secondary-container" size={16} />
              </div>
              <div className="bg-surface-container-lowest text-on-surface p-sm rounded-xl border border-surface-variant shadow-sm">
                <p className="font-body-md text-body-md">
                  Hi! Ask me about workload, difficulty, prerequisites, or professors for an NUS
                  course — grounded in real student reviews.
                </p>
              </div>
            </div>
          )}

          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}

          {loading && (
            <div className="flex gap-sm self-start max-w-[90%]">
              <div className="w-8 h-8 rounded-full bg-secondary-container flex items-center justify-center flex-shrink-0">
                <Icon name="smart_toy" className="text-on-secondary-container" size={16} />
              </div>
              <div className="bg-surface-container-lowest text-on-surface-variant p-sm rounded-xl border border-surface-variant shadow-sm">
                Thinking…
              </div>
            </div>
          )}

          {error && (
            <p className="font-body-sm text-body-sm text-error self-start">{error}</p>
          )}

          <div ref={bottomRef} />
        </div>

        <div className="shrink-0 w-full bg-surface/80 backdrop-blur-md border-t border-surface-variant p-gutter">
          <form
            onSubmit={handleSubmit}
            className="max-w-[900px] mx-auto flex gap-sm items-end relative"
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submitQuestion(input.trim());
                }
              }}
              placeholder="Ask about modules, degree requirements, or prerequisites..."
              rows={1}
              disabled={loading}
              className="w-full bg-surface-container-lowest border border-outline-variant rounded-xl py-sm px-md font-body-md text-body-md text-on-surface focus:border-tertiary focus:ring-0 focus:outline-none resize-none h-14 hide-scrollbar"
            />
            <button
              type="submit"
              aria-label="Send message"
              disabled={loading || !input.trim()}
              className="absolute right-md bottom-3 p-1 bg-primary text-on-primary rounded-lg shadow-[0_4px_12px_rgba(148,74,0,0.2)] hover:bg-primary-container transition-colors disabled:opacity-50"
            >
              <Icon name="send" filled />
            </button>
          </form>
          <div className="max-w-[900px] mx-auto flex gap-2 mt-2 overflow-x-auto hide-scrollbar">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => submitQuestion(s)}
                disabled={loading}
                className="whitespace-nowrap px-3 py-1 rounded-full border border-outline-variant bg-surface-container-lowest text-on-surface-variant font-label-sm text-label-sm font-mono hover:bg-surface-variant transition-colors disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </main>

      <aside className="bg-surface-container-low h-full w-80 hidden xl:flex flex-col border-l border-surface-variant fixed right-0 top-16 z-30">
        <div className="p-gutter overflow-y-auto">
          <h3 className="font-headline-sm text-headline-sm font-semibold text-on-surface mb-md">
            Contextual Details
          </h3>

          {contextSources.length === 0 ? (
            <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-sm text-on-surface-variant font-body-sm text-body-sm">
              Ask a question about a module and the sources behind the answer will show up here.
            </div>
          ) : (
            <div className="flex flex-col gap-sm">
              {contextCourseCodes.length > 0 && (
                <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-sm shadow-sm">
                  <p className="font-label-sm text-label-sm font-mono text-on-surface-variant mb-1">
                    Referenced modules
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {contextCourseCodes.map((code) => (
                      <span
                        key={code}
                        className="bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded font-label-sm text-label-sm font-mono"
                      >
                        {code}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-sm shadow-sm">
                <h4 className="font-headline-sm text-headline-sm text-on-surface mb-sm">
                  Cited Reviews
                </h4>
                <ul className="space-y-2">
                  {contextSources.slice(0, 4).map((s, i) => (
                    <li
                      key={i}
                      className="p-2 rounded border border-surface-variant hover:bg-surface-variant transition-colors"
                    >
                      <div className="flex justify-between font-label-sm text-label-sm font-mono text-on-surface-variant">
                        <span className="text-primary font-bold">{s.course_code ?? "—"}</span>
                        {s.date && <span>{s.date}</span>}
                      </div>
                      <p className="font-body-sm text-body-sm text-on-surface mt-1 line-clamp-3">
                        {s.text}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
