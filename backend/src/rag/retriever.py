"""
retriever.py

Retrieves relevant chunks from the Chroma collection for a user query.

- If the query mentions NUS course code(s) (e.g. "CS2030", "GEA1000",
  "CS1101S"), retrieval is filtered to those courses' chunks first.
- If more than one course code is mentioned (e.g. "compare CS2030S vs
  CS2040S"), each course gets its own independently retrieved and reranked
  k-sized share of results, then they're merged - a single query filtered
  to "either course" and globally reranked can't guarantee both are
  actually represented, since one course's chunks can simply out-rank the
  other's and crowd it out of the top k entirely.
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


def detect_course_codes(query: str) -> list[str]:
    """Every distinct course code mentioned in the query, in order of first
    appearance. Empty list if none found."""
    seen: list[str] = []
    for match in COURSE_CODE_PATTERN.finditer(query.upper()):
        code = match.group(0)
        if code not in seen:
            seen.append(code)
    return seen


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


def _query_chunks(collection, query_embedding, fetch_n: int, where: dict | None = None) -> list[dict]:
    """Run one Chroma query and parse the result into our chunk dict shape."""
    result = collection.query(
        query_embeddings=query_embedding,
        n_results=fetch_n,
        where=where,
    )
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
    return chunks


def retrieve(query: str, k: int = DEFAULT_K, course_code: str | None = None) -> list[dict]:
    """Return relevant chunks for the query, each with metadata.

    - Zero or one course code (explicit `course_code` param, or exactly one
      detected in the query text): a single over-fetch-then-rerank pass,
      truncated to k - same behavior as before.
    - Multiple course codes detected (e.g. a "compare X vs Y" question):
      each course gets its own independent over-fetch-then-rerank pass,
      truncated to k EACH, then merged - so a comparison gets up to k
      chunks per course (not k split across them), and no single course's
      chunks can crowd another's out of the result entirely.
    """
    collection = _get_collection()
    query_embedding = embed_texts([query])
    fetch_n = k * OVERFETCH_MULTIPLIER

    codes = [course_code] if course_code else detect_course_codes(query)

    if len(codes) > 1:
        merged = []
        for code in codes:
            course_chunks = _query_chunks(collection, query_embedding, fetch_n, {"course_code": code})
            course_chunks.sort(key=_rerank_score)
            merged.extend(course_chunks[:k])
        return merged

    code = codes[0] if codes else None
    where = {"course_code": code} if code else None
    chunks = _query_chunks(collection, query_embedding, fetch_n, where)

    # If a course-code filter returned nothing (e.g. course has no data yet),
    # fall back to an unfiltered semantic search rather than returning empty.
    if not chunks and where:
        chunks = _query_chunks(collection, query_embedding, fetch_n)

    chunks.sort(key=_rerank_score)
    return chunks[:k]


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "is CS2030 hard for beginners?"
    for c in retrieve(q):
        print(f"[{c['chunk_type']}] {c['course_code']} (dist={c['distance']:.3f}): {c['text'][:100]}...")
