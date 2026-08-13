"""
generate.py

Builds a prompt from retrieved chunks and calls an LLM (OpenAI) to answer
the user's question, grounded only in the provided context. Returns the
answer plus the source chunks actually used, so callers can render
"based on N reviews for CS2030" style attribution.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from src.rag.retriever import retrieve

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are a helpful assistant answering questions about NUS courses \
using course metadata and student review comments. Answer ONLY using the context \
provided below. If the context does not contain enough information to answer the \
question, say so explicitly rather than guessing or using outside knowledge. \
Keep answers concise. When useful, mention specifics (workload, professors, \
difficulty) drawn directly from the reviews. Some reviews may be short or terse, but they are still valid context. \
If the context contains conflicting information, summarize the range of opinions \
rather than picking one side. In the response, include direct quotes from the reviews when relevant, especially if the review is interesting or funny. \
Each piece of context is labeled with its date where available - for questions where \
currency matters (workload, professors, exam format, syllabus specifics), mention how \
recent the reviews you're drawing on are, especially if they're old or all from one \
period, so the reader can judge how current the information likely still is. \
"""

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Add it to backend/.env or the environment."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def format_context(chunks: list[dict]) -> str:
    blocks = []
    for c in chunks:
        # date is "" for non-review (e.g. metadata/prereq) chunks, which have
        # no meaningful date - omit rather than print an empty field.
        date_part = f" | {c['date']}" if c.get("date") else ""
        label = f"[{c['course_code']} | {c['chunk_type']}{date_part}]"
        blocks.append(f"{label}\n{c['text']}")
    return "\n\n---\n\n".join(blocks)


def answer_question(query: str, k: int = 8, course_code: str | None = None) -> dict:
    chunks = retrieve(query, k=k, course_code=course_code)

    if not chunks:
        return {
            "answer": "I couldn't find any relevant course data to answer that question.",
            "sources": [],
        }

    context = format_context(chunks)
    client = _get_client()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n\n{context}\n\nQuestion: {query}"},
        ],
        temperature=0.3,
    )

    answer = response.choices[0].message.content

    sources = [
        {
            "course_code": c["course_code"],
            "chunk_type": c["chunk_type"],
            "date": c["date"],
            "likes": c["likes"],
            "text": c["text"],
        }
        for c in chunks
    ]

    return {"answer": answer, "sources": sources}


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "is CS2030 hard for beginners?"
    result = answer_question(q)
    print(result["answer"])
    print(f"\n--- based on {len(result['sources'])} chunks ---")
