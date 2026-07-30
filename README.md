# NUSMods Course Review RAG

Answers questions about NUS courses (workload, difficulty, prereqs, professor
mentions, etc.) using course metadata from the NUSMods API and student review
comments scraped from Disqus.

## Structure

- `backend/` — Python scrape/clean/chunk/embed pipeline, RAG retrieval +
  generation, and a FastAPI server.
- `frontend/` — Next.js chat UI that calls the FastAPI backend.

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # then fill in OPENAI_API_KEY
```

Build the data (pilot course list by default — see `PILOT_COURSE_CODES` in
`src/scrape/disqus.py`):

```bash
./refresh.sh
```

This runs scrape -> clean -> chunk -> embed. To target specific courses or
the full catalog:

```bash
./refresh.sh --courses CS2030,CS2040
./refresh.sh --all          # full NUSMods catalog — slow, mind Disqus's ToS
./refresh.sh --retry-failed # (re-)scrape only courses that failed last run
```

Before a full `--all` run, warm the NUSMods metadata cache first — it has
no rate limit and doesn't depend on Disqus, so this keeps that scrape's
only network calls the (rate-limited) Disqus ones:

```bash
python src/scrape/nusmods_api.py --prefetch
```

If `--all`/`--retry-failed` gets interrupted (e.g. Disqus's 1000
calls/hour cap), it's safe to just rerun — already-scraped courses are
skipped (see `--max-age-days`), and failures are recorded to
`data/scrape_state/disqus_failures.json` for `--retry-failed` to pick up.

Run the API:

```bash
uvicorn api:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL defaults to localhost:8000
npm run dev
```

Open http://localhost:3000. The backend must be running on port 8000 (or
whatever `NEXT_PUBLIC_API_URL` points to).

## Pipeline stages (backend/src)

| Stage | Script | Output |
|---|---|---|
| Scrape | `scrape/nusmods_api.py`, `scrape/disqus.py` | `data/raw/<CODE>.json` |
| Clean | `pipeline/clean.py` | `data/processed/<CODE>.json` |
| Chunk | `pipeline/chunk.py` | `data/chunks/chunks.jsonl` |
| Embed | `pipeline/embed.py` | `data/chroma_db/` (local Chroma collection) |
| Retrieve | `rag/retriever.py` | — |
| Generate | `rag/generate.py` | — |
| Eval | `eval/test_questions.py` | — |

Each stage is a standalone script/module so you can re-run just one (e.g.
re-embed without re-scraping).

## Notes

- Scraped/derived data (`backend/data/`) is gitignored — this is for
  personal use, not redistribution, given Disqus's ToS on bulk harvesting.
- Embeddings are local (`sentence-transformers`, `all-MiniLM-L6-v2`) — no
  API cost. Generation uses OpenAI (`gpt-4o-mini` by default, configurable
  via `OPENAI_MODEL`).
- Course code detection in queries uses the pattern `[A-Z]{2,3}\d{4}[A-Z]?`.
- Prerequisites are rendered from NUSMods' structured `prereqTree` (exact
  and/or logic over module codes + minimum grades) rather than its free-text
  description where available, and the raw tree is also kept in Chroma
  metadata for exact checking rather than relying on prose an LLM retrieved.
- Retrieval ranks primarily by semantic similarity, then nudges newer and
  non-reply-thread review chunks slightly ahead of older/reply-chain ones
  of similar relevance (see `rag/retriever.py`).
- Disqus scraping is rate-limit aware (reads Disqus's `X-Ratelimit-*`
  headers to pause/retry across the reset boundary) and resumable — a
  failing course is recorded rather than aborting the whole run; see
  `--retry-failed` above.
