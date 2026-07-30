# NUSMods Course Review RAG — Build Plan

## Goal
Build a RAG system that answers questions about NUS courses (workload, difficulty,
prereqs, professor mentions, etc.) using course metadata from the NUSMods API and
course review comments scraped from Disqus.

## Existing assets
- `disqus.py` — pulls review comments from Disqus for given course
  codes. Uses forum `nusmods-prod`, looks up threads by `ident:<COURSE_CODE>`.
  Currently only handles a hardcoded list of course codes and needs to be extended
  to cover the full catalog.

## Tech stack (defaults — swap freely if you have a preference)
- Python 3.11+
- Embeddings: `sentence-transformers` (local, free) — swap to OpenAI
  `text-embedding-3-small` if API cost is acceptable and quality needs to be higher
- Vector store: ChromaDB (local, file-based, zero infra)
- LLM: whichever provider you have API access to (Claude via `anthropic` SDK is a
  natural fit here)
- Backend API: FastAPI, serving the RAG pipeline over HTTP (needed since the
  frontend is now Next.js, not a Python-rendered UI)
- Frontend: Next.js (App Router) + TypeScript + Tailwind, calling the FastAPI
  backend
- Orchestration: plain Python, no heavyweight framework needed at this scale

## Repo structure to create
```
nusmods-rag/
├── backend/
│   ├── data/
│   │   ├── raw/              # raw scraped JSON per course
│   │   └── processed/        # cleaned, normalized JSON
│   ├── src/
│   │   ├── scrape/
│   │   │   ├── disqus.py            # existing scraper, extended
│   │   │   └── nusmods_api.py       # fetch course metadata from api.nusmods.com
│   │   ├── pipeline/
│   │   │   ├── clean.py             # dedupe, strip HTML, filter spam
│   │   │   ├── chunk.py              # split into embeddable chunks with metadata
│   │   │   └── embed.py              # generate + store embeddings in Chroma
│   │   ├── rag/
│   │   │   ├── retriever.py         # metadata-filtered + semantic retrieval
│   │   │   └── generate.py           # prompt construction + LLM call
│   │   └── eval/
│   │       └── test_questions.py    # golden Q&A set + scoring
│   ├── api.py                        # FastAPI app exposing /chat, /courses etc.
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx                 # main chat UI
│   │   ├── layout.tsx
│   │   └── api/                      # optional Next.js route handlers/proxy
│   ├── components/
│   │   ├── ChatWindow.tsx
│   │   ├── MessageBubble.tsx
│   │   └── SourceCitations.tsx      # shows which reviews backed an answer
│   ├── lib/
│   │   └── api.ts                    # typed fetch wrapper for backend API
│   ├── package.json
│   └── tailwind.config.ts
└── README.md
```

## Phased tasks

### Phase 1 — Full data collection
- [ ] Write `src/scrape/nusmods_api.py`: fetch the full module list from
      `https://api.nusmods.com/v2/{academicYear}/moduleList.json`, then per-module
      detail from `https://api.nusmods.com/v2/{academicYear}/modules/{code}.json`
      (title, description, prereqs, workload, department, MCs).
- [ ] Extend `disqus_scraper.py`: replace the hardcoded `COURSE_CODES` list with
      the full code list from the NUSMods API call above. Keep the identifier-based
      thread lookup (`ident:<CODE>`) already working.
- [ ] Save raw output per course as `data/raw/<CODE>.json` containing both the
      course metadata and the list of review comments. Skip re-fetching if the file
      already exists and is less than N days old (add a `--force` flag to override).
- [ ] Respect Disqus rate limits: keep the existing 0.5s pagination delay and 1s
      between-course delay; do not parallelize requests aggressively.

### Phase 2 — Clean and normalize
- [ ] Write `src/pipeline/clean.py`: strip HTML from comment text, drop comments
      under ~15 characters (likely not real reviews), drop `isSpam`/`isDeleted`
      posts, dedupe identical comment text.
- [ ] Normalize into one schema per course:
      `{code, title, description, prereqs, mcs, department, reviews: [{author, date, text, likes}]}`
- [ ] Write cleaned output to `data/processed/<CODE>.json`.

### Phase 3 — Chunk and embed
- [ ] Write `src/pipeline/chunk.py`:
  - One chunk per course for the metadata/description block.
  - One chunk per review (or merge very short adjacent reviews from the same
    course into a single chunk, capped at ~500 tokens).
  - Every chunk gets metadata: `course_code`, `chunk_type` (`info` | `review`),
    `date`, `likes`.
- [ ] Write `src/pipeline/embed.py`: embed all chunks and upsert into a local
      Chroma collection, keyed so re-runs are idempotent (don't duplicate on
      re-embedding).

### Phase 4 — Retrieval
- [ ] Write `src/rag/retriever.py`:
  - Detect if the query mentions a specific course code (regex for the NUS course
    code pattern, e.g. `[A-Z]{2,3}\d{4}[A-Z]?`); if found, filter retrieval to that
    course's chunks first.
  - If no course code detected, run semantic search across all chunks.
  - Return top-k chunks (default k=8) with metadata attached.

### Phase 5 — Generation
- [ ] Write `src/rag/generate.py`: construct a prompt that includes retrieved
      chunks (clearly separated, with course code + chunk type labeled) and
      instructs the model to answer only from the provided context, and to say so
      explicitly if the reviews don't cover what was asked.
- [ ] Return the answer plus the source chunks used, so the interface can show
      "based on N reviews for CS2030" style attribution.

### Phase 6 — Evaluation
- [ ] Write `src/eval/test_questions.py`: a small hardcoded set of test queries
      (~10–15) with the course code they should retrieve and a rough expected
      answer. Run retrieval and check the right course's chunks come back;
      manually review generated answers for hallucination.

### Phase 7 — Backend API
- [ ] Write `backend/api.py` (FastAPI): expose `POST /chat` (takes a question,
      returns generated answer + source chunks used) and `GET /courses` (returns
      the list of available course codes/titles, for a picker in the UI).
- [ ] Enable CORS for the Next.js dev origin (`http://localhost:3000`).
- [ ] Return sources in a structured shape the frontend can render directly, e.g.
      `{ answer: string, sources: [{course_code, author, date, text, likes}] }`.

### Phase 8 — Next.js frontend
- [ ] Scaffold with `npx create-next-app@latest frontend --typescript --tailwind --app`.
- [ ] `lib/api.ts`: typed fetch wrapper calling the FastAPI backend
      (`NEXT_PUBLIC_API_URL` env var for the base URL).
- [ ] `components/ChatWindow.tsx`: message list + input box, calls `/chat` and
      streams/renders the response.
- [ ] `components/MessageBubble.tsx`: renders a single question/answer pair.
- [ ] `components/SourceCitations.tsx`: renders the review snippets an answer was
      based on (author, date, likes, excerpt) so answers are traceable, collapsible
      under each assistant message.
- [ ] Optional: a course picker (autocomplete over `/courses`) to scope a
      conversation to one course, passed along as context on `/chat` calls.
- [ ] Basic loading/error states for the API calls.

### Phase 9 — Refresh automation
- [ ] Add a `Makefile` or simple shell script that re-runs scrape → clean → chunk
      → embed end to end, skipping unchanged data where possible.
- [ ] (Optional) Add a GitHub Actions workflow to run this on a schedule.

## Notes for whoever (or whatever) implements this
- `disqus.py` currently lives at repo root — move it to
  `backend/src/scrape/disqus.py` as the first step of Phase 1, updating any
  relative paths/imports accordingly.
- Keep scraped/derived data out of version control (`backend/data/` in
  `.gitignore`) — this is meant for personal use, not redistribution, given
  Disqus's ToS on bulk harvesting.
- Prefer small, testable functions per pipeline stage over one monolithic script —
  makes it much easier to re-run just one stage (e.g. re-embed without re-scraping).
- Start end-to-end with 2–3 courses before scaling to the full catalog, to catch
  schema/pipeline issues cheaply.
- Frontend and backend run as two separate dev processes locally (`uvicorn` for
  the API, `next dev` for the frontend) — document both commands in the README.