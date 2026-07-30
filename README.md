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
```

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
