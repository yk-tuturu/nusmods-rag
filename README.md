# NUSMods Course Review RAG

Answers questions about NUS courses (workload, difficulty, prereqs, professor
mentions, etc.) using course metadata from the NUSMods API and student review
comments scraped from Disqus.

## Structure

- `backend/` — Python scrape/clean/chunk/embed pipeline, RAG retrieval +
  generation, and a FastAPI server.
- `frontend/` — Next.js chat UI that calls the FastAPI backend.
- `docker-compose.yml` / `docker-compose.dev.yml` — production (pulls
  prebuilt images from GHCR) and local dev (builds from source) stacks.
- `Caddyfile` — reverse proxy + automatic HTTPS config used in production.
- `refresh_data.sh` — safely refreshes `backend/data` without exposing the
  live backend to a half-written directory (see **For Deployment**).
- `.github/workflows/` — CI/CD (`deploy.yml`) and scheduled/manual data
  refresh pipelines (`scrape-prod.yml`, `scrape-test.yml`).

---

## For Developers

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # then fill in OPENAI_API_KEY
```

`OPENAI_API_KEY` powers both chat generation (`gpt-4o-mini` by default,
configurable via `OPENAI_MODEL`) and embeddings (`text-embedding-3-small`,
see `src/embeddings.py`) — there's no local model to download, both go
through the OpenAI API.

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

### Or: run the whole stack in Docker locally

```bash
docker compose -f docker-compose.dev.yml up --build
```

Builds both images from source (rather than pulling from GHCR) and
publishes 3000/8000 directly to the host — useful for checking the
Dockerfiles themselves still work, or testing against a full stack without
juggling two terminal tabs. To run the scraper this way:

```bash
docker compose -f docker-compose.dev.yml run --rm scraper
```

This writes to `backend/data.new`, not the live `backend/data` (see the
`scraper` service's volume mount) — copy/rename it yourself locally if you
want to actually use the result, since there's no live backend to protect
against a half-written directory in this local-only setup.

### Pipeline stages (backend/src)

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

### Notes

- Scraped/derived data (`backend/data/`) is gitignored — this is for
  personal use, not redistribution, given Disqus's ToS on bulk harvesting.
- Embeddings and chat generation both go through OpenAI's API (see
  `src/embeddings.py` and `src/rag/generate.py`) — no local model, no GPU
  needed, but every embed/query does cost a small amount of API usage.
- Course code detection in queries uses the pattern `[A-Z]{2,3}\d{4}[A-Z]?`.
- Prerequisites are rendered from NUSMods' structured `prereqTree` (exact
  and/or logic over module codes + minimum grades) rather than its free-text
  description where available, and the raw tree is also kept in Chroma
  metadata for exact checking rather than relying on prose an LLM retrieved.
- Retrieval ranks primarily by semantic similarity, then nudges newer and
  non-reply-thread review chunks slightly ahead of older/reply-chain ones
  of similar relevance (see `rag/retriever.py`). The reranking weights were
  originally calibrated for a different embedding model's distance scale —
  see the note in `retriever.py` if results seem off.
- Disqus scraping is rate-limit aware (reads Disqus's `X-Ratelimit-*`
  headers to pause/retry across the reset boundary) and resumable — a
  failing course is recorded rather than aborting the whole run; see
  `--retry-failed` above.

---

## For Deployment

### Architecture

A single VM runs three containers via `docker-compose.yml`: `backend`
(FastAPI, image pulled from GHCR), `frontend` (Next.js, standalone output,
also from GHCR), and `caddy` (reverse proxy + automatic Let's Encrypt
HTTPS — the only service with ports published to the host). `backend` and
`frontend` are reachable only from `caddy` over an internal Docker
network, never directly from the internet.

- `nusadvice.ykkoh.com` → `caddy` → `frontend`
- `api.ykkoh.com` → `caddy` → `backend`

### CI/CD

`.github/workflows/deploy.yml` triggers on every push to `master` (or
manually via the Actions tab — `workflow_dispatch`): builds both
Dockerfiles, pushes them to GHCR (`ghcr.io/<owner>/nusmod-backend` /
`nusmod-frontend`), then SSHes into the VM and runs `docker compose pull &&
docker compose up -d`. Only containers whose image actually changed get
recreated; the VM never builds anything itself or runs `git pull` as part
of this — compose/Caddy config changes need a manual `git pull` on the VM
to take effect.

Required GitHub repo secrets (Settings → Secrets and variables → Actions):
`VM_HOST`, `VM_USER`, `VM_SSH_KEY` (a dedicated deploy keypair, not a
personal one — its public half needs to be in that user's
`~/.ssh/authorized_keys` on the VM).

### First-time VM setup

1. Docker Engine + Compose plugin, git, ufw (22/80/443 allowed) on the VM.
2. Clone the repo to `~/nusmods-rag`.
3. `backend/.env` with a real `OPENAI_API_KEY` (not committed — create by
   hand on the VM).
4. DNS: `A` records for both domains pointing at the VM's **static**
   external IP (promote it from ephemeral first — an ephemeral IP can
   change on VM restart and silently break DNS).
5. `docker compose up -d` once, manually, to bring the stack up for the
   first time and let Caddy provision its certificates (needs DNS already
   resolving and 80/443 actually reachable — check both VPC firewall rules
   *and* `ufw`, they're independent layers).
6. Populate `backend/data` — see below. The site has no course data until
   this has run at least once.

After that, `git push` to `master` handles redeploys on its own.

### Refreshing scraped data

Running the scrape+embed pipeline directly on the VM alongside the live
`backend` was starving it of CPU/memory (embedding used to run a local
model; even now that embedding is a hosted API call, scraping 1000+
courses is still a long-running process worth keeping off the box serving
live traffic). Two ways to refresh data, both safe against the live
backend ever reading a half-written directory:

- **`.github/workflows/scrape-prod.yml`** (recommended) — runs weekly
  (Sunday 03:00 UTC) or on demand, entirely on a GitHub-hosted runner: full
  scrape -> clean -> chunk -> embed, then `rsync`s the result into a
  staging directory on the VM and atomically swaps it into
  `backend/data`, then restarts `backend`. No heavy compute ever touches
  the VM.
- **`./refresh_data.sh`** — the same staging + atomic-swap pattern, run
  locally (on the VM, or anywhere with the repo cloned and `docker
  compose` pointed at the VM's stack). Use this for a manual/ad-hoc
  refresh: `./refresh_data.sh` (default pilot list), `./refresh_data.sh
  --courses CS2030,CS2040`, or `./refresh_data.sh --all`.

**`.github/workflows/scrape-test.yml`** is separate and lower-stakes:
manual-only, scrapes a small fixed course list
(`CS2030S,CS2040S,CS1101S,MA1521,MA1522,GEA1000,CS2103T`), and just uploads
the result as a downloadable Actions artifact — it never touches the VM,
useful for verifying the pipeline still works without any risk to
production data.

### Operating the VM

```bash
docker compose ps                          # container status
docker compose logs backend --tail 50 -f   # live logs for one service
docker stats                               # live CPU/memory per container
docker compose exec backend bash           # shell inside a running container
```
