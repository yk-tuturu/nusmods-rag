"""
retriever.py

Retrieves relevant chunks from the Chroma collection for a user query.

- If the query mentions a specific NUS course code (e.g. "CS2030", "GEA1000",
  "CS1101S"), retrieval is filtered to that course's chunks first.
- Otherwise, semantic search runs across all chunks.
- Ranking is still primarily semantic similarity, but nudged toward newer
  and non-reply-thread review chunks (see _rerank_score): we over-fetch
  from Chroma, then rerank the candidates by a composite score before
  truncating to k, rather than trusting Chroma's raw distance order as-is.

Uses the same OpenAI embedding model as embed.py to embed the query, since
embeddings must come from the same model as the stored vectors.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import chromadb

BACKEND_DIR = Path(__file__).resolve().parents[2]

try:
    from src.embeddings import embed_texts
except ImportError:  # running as a plain script rather than a package module
    import sys
    sys.path.insert(0, str(BACKEND_DIR))
    from src.embeddings import embed_texts

CHROMA_DIR = BACKEND_DIR / "data" / "chroma_db"
COLLECTION_NAME = "nusmods_reviews"
DEFAULT_K = 8

# How many extra candidates to pull from Chroma before reranking, so the
# recency/reply-chain nudge below has something to reorder among near-ties
# instead of only ever seeing Chroma's already-truncated top k.
OVERFETCH_MULTIPLIER = 3

# Recency/reply-chain reranking weights. NOTE: these were calibrated
# against all-MiniLM-L6-v2's typical adjacent-candidate distance gaps of
# ~0.05-0.15 in Chroma's default l2 space. Now that embeddings come from
# OpenAI's text-embedding-3-small (see src/embeddings.py) instead, the
# actual distance-gap scale for this collection hasn't been re-measured -
# these weights may be mis-calibrated (too weak to matter, or strong enough
# to dominate semantic similarity) until checked against real query results.
RECENCY_HALF_LIFE_DAYS = 365 * 2  # a review's recency bonus halves every 2 years
RECENCY_WEIGHT = 0.15
REPLY_THREAD_PENALTY = 0.05

# NUS course code pattern, e.g. CS2030, GEA1000, CS1101S, ST2131
COURSE_CODE_PATTERN = re.compile(r"\b[A-Z]{2,3}\d{4}[A-Z]?\b")

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_or_create_collection(COLLECTION_NAME)
    return _collection


def detect_course_code(query: str) -> str | None:
    match = COURSE_CODE_PATTERN.search(query.upper())
    return match.group(0) if match else None


def _recency_factor(date_str: str | None) -> float:
    """1.0 for a chunk dated right now, halving every RECENCY_HALF_LIFE_DAYS.
    0.0 for chunks with no (parseable) date, so they get no recency bonus."""
    if not date_str:
        return 0.0
    try:
        dt = datetime.fromisoformat(date_str)
    except ValueError:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    return 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)


def _rerank_score(chunk: dict) -> float:
    """Lower is "better", matching Chroma's distance convention. Only
    review chunks get nudged - info chunks have no date/reply-chain concept
    to nudge on."""
    score = chunk["distance"]
    if chunk["chunk_type"] == "review":
        score -= RECENCY_WEIGHT * _recency_factor(chunk["date"])
        if chunk.get("is_thread"):
            score += REPLY_THREAD_PENALTY
    return score


def retrieve(query: str, k: int = DEFAULT_K, course_code: str | None = None) -> list[dict]:
    """Return up to k chunks most relevant to the query, each with metadata.

    Over-fetches k * OVERFETCH_MULTIPLIER candidates from Chroma, then
    reranks them by _rerank_score before truncating to k - semantic
    similarity is still the primary signal, but newer/standalone-comment
    chunks get a nudge ahead of near-tied older/reply-thread ones.
    """
    collection = _get_collection()

    course_code = course_code or detect_course_code(query)
    where = {"course_code": course_code} if course_code else None

    query_embedding = embed_texts([query])
    fetch_n = k * OVERFETCH_MULTIPLIER

    result = collection.query(
        query_embeddings=query_embedding,
        n_results=fetch_n,
        where=where,
    )

    # If a course-code filter returned nothing (e.g. course has no data yet),
    # fall back to an unfiltered semantic search rather than returning empty.
    ids = result.get("ids", [[]])[0]
    if not ids and where:
        result = collection.query(query_embeddings=query_embedding, n_results=fetch_n)
        ids = result.get("ids", [[]])[0]

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    chunks = []
    for id_, doc, meta, dist in zip(ids, documents, metadatas, distances):
        chunks.append({
            "id": id_,
            "text": doc,
            "course_code": meta.get("course_code"),
            "chunk_type": meta.get("chunk_type"),
            "date": meta.get("date"),
            "likes": meta.get("likes"),
            "is_thread": bool(meta.get("is_thread")),
            "distance": dist,
        })

    chunks.sort(key=_rerank_score)
    return chunks[:k]


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "is CS2030 hard for beginners?"
    for c in retrieve(q):
        print(f"[{c['chunk_type']}] {c['course_code']} (dist={c['distance']:.3f}): {c['text'][:100]}...")
