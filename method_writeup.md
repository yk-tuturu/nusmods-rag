# Chunking & Retrieval — Method Writeup

How data gets from raw source (Disqus reviews, NUSMods API, NUS programme
pages) into a single Chroma collection, and how a user's question pulls the
right pieces back out. This is a living doc — update it when the chunking or
retrieval logic changes, not just when it's first written.

## 1. Data sources

Two very different kinds of content feed the same collection:

1. **Per-course data** (`data/raw/<CODE>.json` → `data/processed/<CODE>.json`):
   NUSMods API metadata (title, MCs, prereqs, department) plus scraped Disqus
   review comments, cleaned by `src/pipeline/clean.py` (dedup, spam filter,
   HTML stripped).
2. **Programme/degree-requirement docs** (`programme/<CODE>.md`): hand-
   compiled markdown per major (`CS.md`, `BBA.md`, `BAIS.md`, `BZA.md`,
   `InfoSec.md`) plus one cross-cutting doc for general education (`GE.md`).
   `programme/_common.md` is a third, special case - see §6.

## 2. Chunking (`src/pipeline/chunk.py`)

### 2a. Course chunks

For each processed course, `build_chunks_for_course()` produces:

- **One "info" chunk**: title, MCs, department, prerequisites (rendered from
  the structured prereq tree when available), what it unlocks, S/U-ability,
  and description - everything that isn't a review, in one chunk.
- **One or more "review" chunks**: `group_into_threads()` first groups flat
  Disqus comments into threads (a top-level comment plus its replies, via
  `id`/`parent`), then `build_review_chunks()` packs threads into chunks up
  to `MAX_CHUNK_CHARS` (2000, ~500 tokens). Standalone comments and reply
  threads are kept in separate chunks (never mixed), so a chunk's
  `is_thread` flag is unambiguous - retrieval later deprioritizes threads
  slightly, since a back-and-forth is often lower-signal than one clear
  review.

### 2b. Programme chunks

For each `programme/<CODE>.md` (except files starting with `_`),
`build_programme_chunks()` calls `split_markdown_sections()`, which splits
the document at **every** `#` or `##` header line, regardless of level. The
docs don't nest headers consistently (BBA.md mixes `##` for its intro with
`#` for later sections), so a flat split is more robust than trying to
respect a hierarchy.

- Content before the first header becomes an "Overview" chunk.
- Each header's chunk keeps a reference to the nearest preceding `#`-level
  header as its `parent`, used to disambiguate two same-titled `##`
  sections under different parents - e.g. `GE.md` has two `## Data
  Literacy` sections (one describing the pillar, one listing its approved
  courses); without the parent, a chunker keyed on title alone would
  collide them. The disambiguated title becomes `section_title`, e.g.
  `"List of Courses approved under the GE pillars — Data Literacy"`.
- Each chunk's `text` is prefixed with `"<CODE> programme — <section_title>"`
  so the embedding captures what the section is about even when the body
  text alone doesn't say it (a bare course list doesn't mention its own
  pillar name).

One thing this step doesn't do automatically: catch duplicated content
*within* a source doc. `BBA.md` originally had its intro block pasted three
times (a scrape artifact), which produced one ~11,000-character chunk before
being manually deduplicated. Worth an eyeball check on chunk sizes after
adding a new programme doc (`python src/pipeline/chunk.py` prints a count
per file; a quick script iterating chunk lengths catches outliers - see the
dry run used during implementation).

### 2c. `_common.md` is skipped entirely

It's small (~135 lines) and universally relevant regardless of course or
major, so it doesn't need to compete for retrieval - see §6.

All chunks (course + programme) are written to a single
`data/chunks/chunks.jsonl`, one JSON object per line.

## 3. Embedding (`src/pipeline/embed.py`)

Every chunk is embedded with OpenAI's `text-embedding-3-small` and upserted
into one Chroma collection (`nusmods_reviews`), keyed by chunk id so re-runs
are idempotent. Metadata stored per chunk:

| field | meaning |
|---|---|
| `course_code` | set on info/review chunks, empty string on programme chunks |
| `programme_code` | set on programme chunks (e.g. `"CS"`, `"GE"`), empty string otherwise |
| `section_title` | set on programme chunks only |
| `chunk_type` | `"info"` \| `"review"` \| `"programme"` |
| `date`, `likes`, `is_thread` | review-specific, unused on other types |
| `prereq_tree` | JSON-encoded structured prereq tree, info chunks only |

Any chunk id present in Chroma but no longer in `chunks.jsonl` gets deleted
first, so stale vectors (e.g. from a doc that shrank on re-chunk) don't
linger.

## 4. Retrieval (`src/rag/retriever.py`)

`retrieve(query, k, course_code, history, programme_code, k_programme)`
runs two independent passes and merges them.

### 4a. Course pass (pre-existing, unchanged in spirit)

- If `course_code` is given, or exactly one course code is detected in the
  query text (`COURSE_CODE_PATTERN`, a regex like `\b[A-Z]{2,3}\d{4}[A-Z]?\b`),
  that's a single filtered query, over-fetched 3x and reranked by
  `_rerank_score` (semantic distance, nudged for recency and against reply
  threads on review chunks), truncated to `k`.
- If *multiple* course codes are detected (e.g. "compare X vs Y"), each gets
  its own independent filtered query truncated to `k`, then merged - so a
  comparison always gets up to `k` chunks per course, and neither can crowd
  the other out.
- If no code is detected but `history` is given, falls back to the most
  recently mentioned code in the conversation, so a follow-up question
  ("what about the workload?") inherits the course being discussed.
- If nothing is detected anywhere, an unfiltered semantic search runs -
  explicitly excluding `chunk_type: "programme"` from this fallback (see
  the note in 4c on why that exclusion exists).

### 4b. Programme pass (new)

Handles majors differently from courses because major names don't have a
fixed, regex-matchable format the way course codes do ("CS" vs "Computer
Science" vs "BComp(CS)" vs "comp sci"). Instead, `PROGRAMME_ALIASES` is a
small, hand-maintained lookup (one entry per programme doc that exists),
matched with word-boundary-anchored regexes built once at import
(`detect_programme_codes()`). It only needs to cover the majors actually
present in `programme/`, so it stays small and doesn't need an LLM
classifier or fuzzy matching to be reliable.

The set of programme codes to retrieve for is the union of:

1. Codes detected in the query text itself (`detect_programme_codes`).
2. If none found in the query, codes detected in the most recent relevant
   turn of conversation history (`detect_programme_codes_from_history`).
3. The `programme_code` parameter, if the caller passed one (e.g. from a
   frontend major selector) - unioned in, not just used as a fallback. This
   is deliberate: "I'm doing BBA but what does CS need" should surface
   *both* CS and BBA content, not silently prefer one.

**If this union ends up empty, the whole programme pass is skipped.** An
ordinary course-review question ("is CS2030S hard?") gets no programme
chunks forced into it just because the pass always runs - there's no
textual or explicit signal that it's programme-related, so it stays out of
the way. Only once something *does* trigger the pass does `"GE"` get added
automatically to the code set, since general-education content is relevant
alongside whatever major triggered it, without requiring "GE" to be
separately detected every time.

For each code in the final set, `_retrieve_programme_chunks()` runs an
independent query filtered to `{"chunk_type": "programme", "programme_code": <code>}`,
over-fetched and sorted by raw distance (no recency nudge - these aren't
dated), truncated to `k_programme` (default 3) - same "never let one crowd
out another" reasoning as the multi-course-code case in 4a, so a
CS-vs-BBA comparison guarantees both are represented rather than one
out-ranking the other into oblivion.

### 4c. Why the main pass excludes programme chunks

Early testing surfaced a real problem: an *unfiltered* semantic search for
"how many units does CS need" was pulling in InfoSec's and BAIS's
degree-requirement chunks too, purely because their boilerplate text
("Bachelor of Computing... 160 units... Common Curriculum Requirements...")
is semantically close to CS's own boilerplate. That's confusing, wrong-major
noise a course-review question shouldn't have to filter out itself - the
dedicated programme pass in 4b already exists to retrieve the *correct*
majors' content deliberately, so the main pass now explicitly excludes
`chunk_type: "programme"` (via a `$ne` filter) whenever it isn't already
scoped to a specific `course_code` (which excludes programme chunks
implicitly anyway, since they have no course code).

### 4d. Merge and dedup

The two passes' results are combined, deduplicated by chunk id (a chunk
that happens to appear in both is only kept once), programme chunks
appended after course chunks.

## 5. Generation (`src/rag/generate.py`)

- `format_context()` labels each chunk block differently by type:
  `[<course_code> | review | <date>]` / `[<course_code> | info]` for course
  chunks, `[<programme_code> programme | <section_title>]` for programme
  chunks.
- `SYSTEM_PROMPT` tells the model that `"programme"`-labeled context is
  factual degree-structure data straight from NUS documents, not student
  opinion - so the sarcasm/conflicting-opinions handling that applies to
  reviews doesn't apply there. It also has a MANDATORY clause: if a
  "programme" entry lists the course being discussed as compulsory/core/
  required, the answer must say so explicitly and plainly, not just as
  something softer like "foundational."
- **That system-prompt clause alone wasn't reliable enough on its own**
  (tested empirically: 0/3 hit rate with only the system-prompt version,
  since it's one instruction competing with a long prompt plus the entire
  contents of `_common.md` appended after it). `answer_question()` also
  repeats a short version of the same instruction in the **per-turn user
  message**, right next to that turn's actual Context, conditioned on
  whether any retrieved chunk this turn is actually `chunk_type ==
  "programme"` - proximity and recency get followed far more reliably than
  a standing rule stated once, further up, in the abstract (3/3 after
  adding this).
- **The inverse case needed explicit suppression, not silence.** Once the
  model had been primed to talk about "required" courses, testing showed it
  would sometimes assert a course was "compulsory" from its own pretrained
  knowledge of real NUS courses even when *no* programme chunk was present
  in that turn's Context at all - simply not mentioning the instruction
  wasn't enough to stop this. The fix: when no programme chunk was
  retrieved this turn, the per-turn reminder actively tells the model *not*
  to state or imply required/elective status for any course, even one it
  recognizes, rather than just staying quiet on the topic.
- `answer_question()` threads `programme_code` through to `retrieve()`
  unchanged from what the caller passed.

## 6. `_common.md`: static injection, not retrieval

`programme/_common.md` holds small, universally-true facts: NUS
terminology (MC, CAP, S/U, ULR, Honours, course-level numbering, NOC), the
grading scale, module load/overloading rules, the six GE pillar names, and
the two different "common curriculum" shapes seen so far (School of
Computing's 40-unit pattern vs Business School's 52-unit pattern - these
are genuinely different, not just reworded, so the doc keeps them separate
rather than presenting one blended "common curriculum" that would be wrong
for whichever school it wasn't written for).

It bypasses chunking/embedding entirely. `generate.py` reads it once at
import time and appends it to `SYSTEM_PROMPT`, so it's present on every
request regardless of what retrieval finds - it doesn't need to compete for
relevance since it's small (~1,800 tokens) and always applicable.

## 7. Frontend wiring

- `GET /programmes` (`api.py`) lists selectable majors - one per
  `programme/<CODE>.md`, excluding `_common.md` (not a major) and
  `GE.md` (applies to everyone automatically, not something a student
  "selects").
- `ChatInterface.tsx` has a "Major:" selector next to the existing course
  "Scope:" selector, both populated from the backend (`/programmes`,
  `/courses`) rather than hardcoded, so adding a new programme doc makes it
  selectable without a frontend change.
- The selected major is sent as `programme_code` on every `/chat` request
  and flows through `answer_question()` → `retrieve()` as described in §4b.
  Selecting "No major selected" just means the programme pass only fires
  when a major is actually named in the chat text.

## 8. Known limitations / things to revisit

- **Alias list is hand-maintained.** `PROGRAMME_ALIASES` needs a new entry
  whenever a programme doc is added. If phrasing turns out to slip through
  in practice (typos, very novel colloquialisms), the fallback discussed
  but not built is a single structured-output LLM classification call - not
  a multi-agent pipeline, since this is a bounded classification problem
  against a small enum, not something needing iterative reasoning.
- **GE course-list chunks are still fairly large** (Digital Literacy and
  Critique and Expression sections run ~4,500 characters each) even after
  per-pillar splitting. Not yet a demonstrated problem, but if retrieval
  precision on GE questions turns out to suffer, the next cut is by the
  `GE%-CODED` / `NON-GE%-CODED` sub-groups already visible in the source
  text.
- **No staleness detection yet.** Programme docs are manually copied from
  NUS registrar/faculty pages with no freshness tracking. A cheap
  hash-diff-based check against the source URLs (rather than an AI
  scraping agent, given how infrequently these pages change) was discussed
  as the long-term direction but isn't implemented.
