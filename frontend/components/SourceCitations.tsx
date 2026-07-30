"use client";

import { useState } from "react";
import type { SourceChunk } from "@/lib/api";

export default function SourceCitations({ sources }: { sources: SourceChunk[] }) {
  const [expanded, setExpanded] = useState(false);

  if (sources.length === 0) return null;

  const courseCodes = Array.from(
    new Set(sources.map((s) => s.course_code).filter(Boolean))
  );

  return (
    <div className="mt-2 text-sm">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 underline underline-offset-2"
      >
        {expanded ? "Hide" : "Show"} sources ({sources.length} chunk
        {sources.length === 1 ? "" : "s"}
        {courseCodes.length > 0 ? ` — ${courseCodes.join(", ")}` : ""})
      </button>

      {expanded && (
        <ul className="mt-2 space-y-2">
          {sources.map((s, i) => (
            <li
              key={i}
              className="rounded-md border border-zinc-200 dark:border-zinc-700 p-2 bg-zinc-50 dark:bg-zinc-900"
            >
              <div className="flex flex-wrap gap-x-2 text-xs text-zinc-500 mb-1">
                {s.course_code && <span className="font-medium">{s.course_code}</span>}
                {s.chunk_type && <span>[{s.chunk_type}]</span>}
                {s.date && <span>{s.date}</span>}
                {typeof s.likes === "number" && s.likes > 0 && <span>{s.likes} likes</span>}
              </div>
              <p className="text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap">
                {s.text.length > 400 ? `${s.text.slice(0, 400)}…` : s.text}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
