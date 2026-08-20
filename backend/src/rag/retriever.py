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

Programme/degree-requirement content (chunk_type == "programme", see
chunk.py's build_programme_chunks) is retrieved in a second, independent
pass and merged in - see detect_programme_codes() and retrieve()'s
docstring. Unlike course chunks, this pass only runs when there's an actual
signal that the query is programme-related (a major named in the text, in
recent history, or explicitly selected by the caller), so a plain course
review question never gets an unrelated degree-requirement chunk forced
into its context just because the pass always fires.

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
# Kept deliberately small relative to DEFAULT_K - programme docs are a
# handful of already-focused sections (see chunk.py), not a large pool of
# reviews, so a couple of chunks per matched major/GE is usually enough.
DEFAULT_K_PROGRAMME = 3

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


def detect_course_codes_from_history(history: list[str]) -> list[str]:
    """Course codes from prior conversation turns, for follow-ups that don't
    repeat a code themselves (e.g. "what about the workload?" after a
    message about CS2030S). Scans most-recent-first and returns the codes
    from the first (most recent) turn that mentions any, so a newer course
    mentioned later in the conversation takes precedence over an older one -
    it does not merge codes across turns."""
    for message in reversed(history):
        codes = detect_course_codes(message)
        if codes:
            return codes
    return []


# Colloquial ways students refer to a programme, mapped to the
# programme_code used in programme/<code>.md (and thus in chunk
# metadata). Unlike course codes, major names don't follow a fixed format
# ("CS" vs "Computer Science" vs "BComp(CS)"), so this is a maintained
# lookup rather than a regex pattern - it only needs an entry per major
# actually covered by a doc in programme/, so it stays small. "GE"
# isn't a major but gets the same treatment since general-education
# questions are asked the same way ("what GE courses satisfy X").
PROGRAMME_ALIASES: dict[str, list[str]] = {
    "CS": ["computer science", "comp sci", "cs", "bcomp(cs)", "bcomp cs"],
    "BBA": ["business administration", "bba"],
    "BAIS": ["business artificial intelligence systems", "bais"],
    "BZA": ["business analytics", "bza"],
    "InfoSec": ["information security", "infosec", "info security", "cybersecurity"],
    "GE": ["general education", "gen ed", "ge pillar", "ge pillars"],
}

# One compiled pattern per alias, each anchored with \b so e.g. the bare
# alias "cs" matches the standalone word "cs" but not the "cs" inside
# "cs2030" (no word boundary between "s" and "2", since digits count as
# word characters) - built once at import time rather than per call.
_PROGRAMME_ALIAS_PATTERNS: list[tuple[str, re.Pattern]] = [
    (code, re.compile(r"\b" + re.escape(alias) + r"\b", re.IGNORECASE))
    for code, aliases in PROGRAMME_ALIASES.items()
    for alias in aliases
]


def detect_programme_codes(query: str) -> list[str]:
    """Every distinct programme_code whose alias appears in the query, in
    PROGRAMME_ALIASES definition order (not order of appearance in the
    text - unlike detect_course_codes, since a query naming several majors
    doesn't imply any ordering between them). Empty list if none found."""
    seen: list[str] = []
    for code, pattern in _PROGRAMME_ALIAS_PATTERNS:
        if code not in seen and pattern.search(query):
            seen.append(code)
    return seen


def detect_programme_codes_from_history(history: list[str]) -> list[str]:
    """Same idea as detect_course_codes_from_history: scans most-recent-first
    and returns the programme codes from the first (most recent) turn that
    mentions any."""
    for message in reversed(history):
        codes = detect_programme_codes(message)
        if codes:
            return codes
    return []


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
            # Only meaningful on "programme" chunks (see chunk.py).
            "programme_code": meta.get("programme_code") or None,
            "section_title": meta.get("section_title") or None,
            "distance": dist,
        })
    return chunks


def _retrieve_programme_chunks(
    collection,
    query_embedding,
    codes: set[str],
    k_programme: int,
) -> list[dict]:
    """One query per programme code, each truncated to k_programme and then
    merged - same "never let one crowd out another" reasoning as the
    multi-course-code path in retrieve(), applied to majors instead of
    courses (e.g. so a "CS vs BBA" comparison doesn't lose one major's
    content just because the other's sections happen to rank higher)."""
    fetch_n = k_programme * OVERFETCH_MULTIPLIER
    merged: list[dict] = []
    seen_ids: set[str] = set()
    for code in codes:
        where = {"$and": [{"chunk_type": "programme"}, {"programme_code": code}]}
        code_chunks = _query_chunks(collection, query_embedding, fetch_n, where)
        code_chunks.sort(key=lambda c: c["distance"])
        for c in code_chunks[:k_programme]:
            if c["id"] not in seen_ids:
                merged.append(c)
                seen_ids.add(c["id"])
    return merged


def retrieve(
    query: str,
    k: int = DEFAULT_K,
    course_codes: list[str] | None = None,
    history: list[str] | None = None,
    programme_codes: list[str] | None = None,
    k_programme: int = DEFAULT_K_PROGRAMME,
) -> list[dict]:
    """Return relevant chunks for the query, each with metadata.

    - Zero or one course code (explicit `course_codes` param, or exactly one
      detected in the query text): a single over-fetch-then-rerank pass,
      truncated to k - same behavior as before.
    - Multiple course codes (explicit `course_codes` param, e.g. a frontend
      scope multi-select, or several detected in the query text, e.g. a
      "compare X vs Y" question): each course gets its own independent
      over-fetch-then-rerank pass, truncated to k EACH, then merged - so a
      comparison gets up to k chunks per course (not k split across them),
      and no single course's chunks can crowd another's out of the result
      entirely.
    - No course code in the query itself and no explicit `course_codes` but
      `history` is given: falls back to the most recent course code(s)
      mentioned earlier in the conversation, so a follow-up question
      inherits the course being discussed instead of losing the filter.

    Programme/degree-requirement chunks are then retrieved in a second pass
    and appended (deduplicated by id):
    - Any major named in the query text or recent history (via
      detect_programme_codes) always gets its own guaranteed slice.
    - `programme_codes` (e.g. a frontend major multi-select) are unioned in
      too, even if the query names a *different* major - so "I'm doing BBA
      but what does CS need" surfaces both instead of silently picking one.
    - This whole pass is skipped if neither of the above found anything, so
      an ordinary course-review question never gets a forced, likely
      irrelevant programme chunk added just because the pass always runs.
      Once it does run, "GE" (general education) is always included
      alongside whatever major(s) triggered it, since GE content is
      relevant regardless of major.
    """
    collection = _get_collection()
    query_embedding = embed_texts([query])
    fetch_n = k * OVERFETCH_MULTIPLIER

    codes = list(course_codes) if course_codes else detect_course_codes(query)
    if not codes and history:
        codes = detect_course_codes_from_history(history)

    if len(codes) > 1:
        chunks = []
        for code in codes:
            course_chunks = _query_chunks(collection, query_embedding, fetch_n, {"course_code": code})
            course_chunks.sort(key=_rerank_score)
            chunks.extend(course_chunks[:k])
    else:
        code = codes[0] if codes else None
        # Excludes "programme" chunks specifically from the *unfiltered*
        # semantic search - a real course_code filter already excludes them
        # implicitly (programme chunks have no course_code), but without
        # this, an unfiltered query can pull in another major's programme
        # chunk purely because its boilerplate ("Bachelor of Computing...
        # 160 units...") is semantically close, which is confusing noise
        # for a course-review question and is what the dedicated
        # _retrieve_programme_chunks pass below exists to handle properly.
        where = {"course_code": code} if code else {"chunk_type": {"$ne": "programme"}}
        chunks = _query_chunks(collection, query_embedding, fetch_n, where)

        # If a course-code filter returned nothing (e.g. course has no data yet),
        # fall back to an unfiltered (but still non-programme) semantic search
        # rather than returning empty.
        if not chunks and code:
            chunks = _query_chunks(collection, query_embedding, fetch_n, {"chunk_type": {"$ne": "programme"}})

        chunks.sort(key=_rerank_score)
        chunks = chunks[:k]

    detected_programme_codes = set(detect_programme_codes(query))
    if not detected_programme_codes and history:
        detected_programme_codes = set(detect_programme_codes_from_history(history))
    if programme_codes:
        detected_programme_codes.update(programme_codes)

    if detected_programme_codes:
        detected_programme_codes.add("GE")
        programme_chunks = _retrieve_programme_chunks(
            collection, query_embedding, detected_programme_codes, k_programme
        )
        seen_ids = {c["id"] for c in chunks}
        for pc in programme_chunks:
            if pc["id"] not in seen_ids:
                chunks.append(pc)
                seen_ids.add(pc["id"])

    return chunks


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "is CS2030 hard for beginners?"
    for c in retrieve(q):
        label = c["course_code"] or f"{c['programme_code']}/{c['section_title']}"
        print(f"[{c['chunk_type']}] {label} (dist={c['distance']:.3f}): {c['text'][:100]}...")
