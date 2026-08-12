"use client";

import { useState } from "react";
import type { SourceChunk } from "@/lib/api";
import Icon from "@/components/Icon";

export default function SourceCitations({ sources }: { sources: SourceChunk[] }) {
  const [expanded, setExpanded] = useState(false);

  const courseCodes = Array.from(
    new Set(sources.map((s) => s.course_code).filter(Boolean))
  );

  return (
    <div className="mt-xs">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="font-label-sm text-label-sm font-mono text-secondary hover:underline flex items-center gap-1 w-max"
      >
        <Icon name="description" size={14} />
        Source: {sources.length} review chunk{sources.length === 1 ? "" : "s"}
        {courseCodes.length > 0 ? ` — ${courseCodes.join(", ")}` : ""}
        <Icon name={expanded ? "expand_less" : "expand_more"} size={14} />
      </button>

      {expanded && (
        <ul className="mt-xs space-y-xs">
          {sources.map((s, i) => (
            <li
              key={i}
              className="rounded-lg border border-outline-variant p-sm bg-surface-bright"
            >
              <div className="flex flex-wrap gap-x-2 font-label-sm text-label-sm font-mono text-on-surface-variant mb-1">
                {s.course_code && <span className="font-bold text-primary">{s.course_code}</span>}
                {s.chunk_type && <span>[{s.chunk_type}]</span>}
                {s.date && <span>{s.date}</span>}
                {typeof s.likes === "number" && s.likes > 0 && <span>{s.likes} likes</span>}
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant whitespace-pre-wrap">
                {s.text.length > 400 ? `${s.text.slice(0, 400)}…` : s.text}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
