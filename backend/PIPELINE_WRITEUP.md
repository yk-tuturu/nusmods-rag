# NUSMods RAG: Data & Embedding Pipeline

This document describes the full pipeline that turns raw NUSMods module metadata
and Disqus review comments into the vector store the RAG API queries at runtime.
It reflects the code as of this writing in `backend/src/`.

The pipeline is four stages, each a standalone script, chained together by
[`refresh.sh`](refresh.sh):

```
scrape (disqus.py) -> clean (clean.py) -> chunk (chunk.py) -> embed (embed.py)
```

```
./refresh.sh                       # refresh the pilot course list
./refresh.sh --courses CS2030,CS2040
./refresh.sh --all                 # full NUSMods catalog (slow)
./refresh.sh --force               # ignore scrape cache freshness
```

Any arguments given to `refresh.sh` are forwarded only to the scrape step;
clean/chunk/embed always operate over whatever is currently on disk in
`data/raw/` and `data/processed/`.

---

## 1. Scrape — `src/scrape/nusmods_api.py` + `src/scrape/disqus.py`

Two data sources are combined per course:

- **NUSMods API** (`nusmods_api.py`, `https://api.nusmods.com/v2`) — module
  metadata: title, description, prerequisite tree, MCs, department, faculty,
  workload, preclusions, `fulfillRequirements` (reverse-prereq edges), and
  whether the module is S/U-able. Responses are cached to disk at
  `data/.cache/nusmods/<academicYear>/` since the catalog barely changes
  within a year. `python nusmods_api.py --prefetch` warms this cache for the
  entire catalog up front (NUSMods has no rate limit), so a subsequent
  `disqus.py --all` run never has to hit NUSMods over the network.
- **Disqus** (`disqus.py`) — the review comments embedded on each NUSMods
  course page, fetched via the Disqus public API (`disqus.com/api/3.0`,
  forum shortname `nusmods-prod`). For each course it looks up the Disqus
  thread by `ident:<course_code>`, then pages through `threads/listPosts.json`
  (100 posts/page) to collect every comment.

Disqus's free tier caps requests at 1000/hour. `_disqus_get()` reads the
`X-Ratelimit-Remaining` / `X-Ratelimit-Reset` headers Disqus returns on
*every* response (including errors — a quota-exhausted request comes back as
a plain HTTP 400, not 429) and sleeps until the reset boundary rather than
guessing a fixed backoff.

Each course's scrape result is written to `data/raw/<CODE>.json`:

```json
{
  "code": "CS2030",
  "metadata": { "moduleCode", "title", "description", "prerequisite",
                "prereqTree", "preclusion", "fulfillRequirements",
                "moduleCredit", "department", "faculty", "workload", "su" },
  "reviews": [
    { "id": "...", "parent": "...", "author": "...", "createdAt": "...",
      "likes": 0, "dislikes": 0, "text": "...", "is_spam": false,
      "is_deleted": false }
  ],
  "scraped_at": "..."
}
```

`id`/`parent` come straight from Disqus's post ids and thread-reply
relationships, and are what `chunk.py` later uses to reassemble reply
threads. Comment text has its HTML stripped and entities unescaped at scrape
time (`clean_html()` in `disqus.py`).

By default only a small pilot set of course codes is scraped
(`PILOT_COURSE_CODES` in `disqus.py`: CS2030, CS2040, CS1101S, MA1521,
GEA1000, CS3230, IS1108). `--all` scrapes the full catalog; `--courses`
targets specific codes. A per-course cache freshness check (`is_fresh`,
default 7 days) skips re-scraping unless `--force` is passed. Any course that
throws during scraping is recorded to `data/scrape_state/disqus_failures.json`
(with attempt count / last error / timestamp) instead of aborting the whole
run, and `--retry-failed` re-scrapes only those.

---

## 2. Clean — `src/pipeline/clean.py`

Reads every file in `data/raw/` and writes a normalized version to
`data/processed/<CODE>.json`:

```json
{
  "code": str, "title": str, "description": str,
  "prereqs": str, "prereq_tree": dict|None, "preclusion": str|None,
  "fulfill_requirements": [str],
  "mcs": str, "department": str, "su": bool,
  "reviews": [
    { "id": str|None, "parent": str|None, "author": str,
      "date": str, "text": str, "likes": int }
  ]
}
```

Review cleaning rules (`clean_reviews()`):

- Drop posts flagged `is_spam` or `is_deleted`.
- Strip HTML tags / unescape entities again defensively (`clean_html()` —
  the raw scrape should already be clean, but this re-runs the same
  transform in case raw data came from elsewhere).
- Drop comments under `MIN_REVIEW_LENGTH` = 15 characters (not likely to be
  real reviews).
- Dedupe: if the cleaned text has been seen before *within the same
  course*, drop the repeat.

Course-level metadata is passed through close to as-is (`prereq_tree`
straight from NUSMods' `prereqTree`; `su` from `attributes.su`, defaulting to
`False` when absent — treated as "not S/U-able," not "unknown").

---

## 3. Chunk — `src/pipeline/chunk.py`

Reads every file in `data/processed/` (or a `--courses` subset) and produces
**one flat JSONL file**, `data/chunks/chunks.jsonl`, containing every
embeddable chunk across every course:

```json
{"id": str, "course_code": str, "chunk_type": "info"|"review",
 "text": str, "date": str|None, "likes": int|None, "is_thread": bool,
 "prereq_tree": dict|None}
```

Two chunk types are produced per course:

**`info` chunk** (`build_info_chunk`, id `"<CODE>_info"`, at most one per
course): a single block of prose assembled from, in order — course code +
title, modular credits, department, prerequisites, "required for" (reverse
prereqs), S/U-able status, and description.

- Prerequisites prefer the *structured* `prereq_tree` over the free-text
  `prereqs` string: `format_prereq_tree()` (in `nusmods_api.py`) renders the
  nested and/or tree of `MODULECODE:GRADE` leaves into a readable boolean
  expression, e.g. `"(CS2040 or CS2040S, min grade D) and (CS1231 or
  CS1231S, min grade D)"`. Free-text `prereqs` is only used as a fallback
  when there's no tree.
- `fulfill_requirements` (modules that list this one as a prereq) is capped
  at 8 shown codes (`FULFILL_REQUIREMENTS_CAP`), appending `", and N more"`
  if truncated — some modules unlock 40+ downstream modules and would
  otherwise dominate the chunk.
- The raw `prereq_tree` dict is also carried alongside the rendered text (not
  just the prose) so `embed.py` can store it as exact-checkable metadata
  rather than relying on the LLM to parse boolean logic back out of prose.
- Returns `None` (no chunk emitted) if the course has no title, MCs,
  department, prereqs, fulfill-requirements, or description at all.

**`review` chunks** (`build_review_chunks`, ids `"<CODE>_review_<idx>"`, zero
or more per course):

1. Reviews are grouped into **threads** (`group_into_threads`): each
   top-level comment plus its replies, recursively, via the `id`/`parent`
   fields, sorted chronologically at every level. A reply whose parent was
   dropped during cleaning (spam/dedupe) or wasn't captured (older scrapes
   predating id/parent) simply becomes its own top-level thread — so courses
   without reply-chain data chunk exactly as they did before this feature
   existed.
2. Each thread is rendered to text (`format_thread`): the root comment's text
   as-is, then each reply on its own line, indented `"  " * depth` and
   prefixed `"↳ <author> replied: "` — since replies are often a
   back-and-forth between two *different* students rather than the original
   reviewer elaborating, and an unlabeled multi-person thread would read as
   one garbled paragraph.
3. Threads are packed into chunks up to `MAX_CHUNK_CHARS` = 2000 (~500 tokens
   at ~4 chars/token). A single thread already at or over that size becomes
   its own chunk; otherwise threads are accumulated into a buffer and
   flushed into a chunk once the next thread would push it over the cap.
4. Critically, **standalone comments and reply threads are buffered and
   flushed separately** (`buffers[False]` / `buffers[True]`, keyed by
   `is_thread = len(thread) > 1`) — they are never merged into the same
   chunk. This keeps each chunk's `is_thread` metadata flag unambiguous
   (never "part of this chunk had replies, part didn't"), which
   `retriever.py` relies on to consistently deprioritize reply-thread chunks.
5. A merged chunk's `date` is the **most recent** thread's date it contains
   (`max(...)`, not the oldest/first), and `likes` is the sum across all
   reviews folded into it — again so recency-based reranking downstream
   isn't working off a stale timestamp.

`chunk.py` can be run standalone (`python chunk.py [--courses CODE,...]`) and
always rewrites the entire `chunks.jsonl` from whatever is currently in
`data/processed/` — it's not incremental across courses.

---

## 4. Embed — `src/pipeline/embed.py`

This is the step that actually populates the vector store queried at
runtime.

**Model**: [`all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
via `sentence-transformers`, loaded locally (no API calls, no cost) —
`SentenceTransformer(EMBEDDING_MODEL)`. This is the exact same model
`retriever.py` uses to embed incoming queries; the constant is duplicated in
both files rather than shared, so if it's ever changed it must be changed in
both places for query/document embeddings to stay compatible.

**Store**: a persistent local Chroma collection at `data/chroma_db/`
(`chromadb.PersistentClient`), single collection named `"nusmods_reviews"`,
created if absent via `get_or_create_collection`. Chroma's default distance
space is used (L2) — `retriever.py`'s reranking weights are explicitly
calibrated against this collection's typical distance gaps, so switching
distance metrics would require re-tuning those constants too.

**Process** (`embed_and_upsert`):

1. Load every line of `data/chunks/chunks.jsonl` (or accept an in-memory
   `chunks` list — the same function is reusable without going through the
   file, though the CLI entry point always reads from disk).
2. **Stale-vector cleanup, run first**: compute the set of chunk ids
   currently in `chunks.jsonl` vs. the set of ids already in the Chroma
   collection (`collection.get(ids=None)`); any id present in Chroma but no
   longer in `chunks.jsonl` is deleted before anything is re-embedded. This
   matters because chunk ids are positional for reviews
   (`<CODE>_review_<idx>`) — if a course produces fewer review chunks on a
   re-chunk (e.g. some comments got cleaned out), its old high-index ids
   would otherwise linger in the collection forever and keep getting
   returned by retrieval.
3. **Batch embed + upsert**, `BATCH_SIZE` = 64 chunks at a time:
   - `texts = [c["text"] for c in batch]` is encoded via
     `model.encode(texts, show_progress_bar=False)`.
   - `collection.upsert(ids=..., embeddings=..., documents=texts,
     metadatas=...)` — keyed by chunk id, so re-running this after a re-chunk
     is idempotent: an unchanged chunk id gets its vector silently
     overwritten with the same value, not duplicated.
4. Metadata stored per chunk (`chunk_metadata()`), used later for filtering
   and reranking in `retriever.py`:
   - `course_code`, `chunk_type`, `date`, `likes` — passed through
     (`None`/missing coerced to `""` / `0` since Chroma metadata values must
     be scalars, not `null`).
   - `is_thread` — coerced to `bool`; only meaningful on review chunks.
   - `prereq_tree` — **JSON-encoded to a string** (`""` if absent) since
     Chroma metadata values must be scalars; this lets a prereq check at
     query time walk the exact and/or tree instead of trusting an LLM to
     parse boolean logic out of the embedded prose.
5. Prints progress per batch and a final count via `collection.count()`.

Running `python embed.py` directly re-embeds from `chunks.jsonl` on disk end
to end; `refresh.sh` invokes it as the last of its four steps.

---

## Downstream: how the embeddings get used

Not part of the embedding pipeline itself, but the consumer that shapes its
design (`src/rag/retriever.py`):

- Queries are embedded with the *same* `all-MiniLM-L6-v2` model (required —
  embeddings from different models aren't comparable).
- If the query text contains something matching an NUS course-code pattern
  (`\b[A-Z]{2,3}\d{4}[A-Z]?\b`, e.g. `CS2030`, `GEA1000`, `CS1101S`),
  retrieval is filtered to that course via Chroma's `where={"course_code":
  ...}`, falling back to an unfiltered search if the filter returns nothing
  (e.g. a course with no data yet).
- Chroma is over-fetched at `k * OVERFETCH_MULTIPLIER` (3x) candidates, then
  reranked client-side (`_rerank_score`) before truncating to `k` (default
  8): review chunks get a recency bonus (half-life 2 years) subtracted from
  their distance, and reply-thread chunks (`is_thread`) get a small penalty
  added, both small enough to only break near-ties rather than override
  genuine semantic relevance. `info` chunks are left unscored/unchanged since
  they have no date or reply-chain concept.

## Key invariants to preserve if this pipeline is modified

- `retriever.py`'s `EMBEDDING_MODEL` constant must always match `embed.py`'s.
- Chunk ids must stay stable across re-chunks for unchanged content
  (`embed.py`'s upsert-idempotency and stale-id cleanup both depend on this),
  and review-chunk ids are positional per course, which is why the stale-id
  sweep runs before every embed.
- A chunk's `is_thread` metadata must never mix standalone and reply-thread
  content — `chunk.py`'s two-buffer split enforces this, and
  `retriever.py`'s reranking assumes it holds.
- `prereq_tree` is only ever set on `info` chunks; `date`/`likes`/`is_thread`
  are only ever meaningful on `review` chunks.
