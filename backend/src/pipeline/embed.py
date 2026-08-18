"""
embed.py

Embeds chunks from data/chunks/chunks.jsonl (see chunk.py) using OpenAI's
embeddings API and upserts them into a persistent local Chroma collection.
Upserts are keyed by chunk id, so re-running this after a re-chunk is
idempotent (no duplicate vectors). Any id present in the collection but no
longer in chunks.jsonl (e.g. a course produced fewer chunks on re-chunk, so
its old high-index ids no longer exist) is deleted first, so stale vectors
never linger and get returned by retrieval. Any id whose text is unchanged
from what's already stored is skipped entirely - no embedding API call, no
upsert - so a chunks.jsonl that's mostly identical to last run (e.g. a
programme-only rebuild that still carries every existing course chunk
verbatim) doesn't re-embed the whole collection every time.

USAGE
-----
python embed.py
"""

from __future__ import annotations

import json
from pathlib import Path

import chromadb

BACKEND_DIR = Path(__file__).resolve().parents[2]

try:
    from src.embeddings import embed_texts
except ImportError:  # running as a plain script rather than a package module
    import sys
    sys.path.insert(0, str(BACKEND_DIR))
    from src.embeddings import embed_texts

CHUNKS_PATH = BACKEND_DIR / "data" / "chunks" / "chunks.jsonl"
CHROMA_DIR = BACKEND_DIR / "data" / "chroma_db"
COLLECTION_NAME = "nusmods_reviews"
BATCH_SIZE = 64


def load_chunks() -> list[dict]:
    chunks = []
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(COLLECTION_NAME)


def chunk_metadata(chunk: dict) -> dict:
    prereq_tree = chunk.get("prereq_tree")
    return {
        "course_code": chunk.get("course_code") or "",
        "chunk_type": chunk.get("chunk_type") or "",
        "date": chunk.get("date") or "",
        "likes": chunk.get("likes") or 0,
        # Only meaningful on "review" chunks - retriever.py uses it to
        # slightly deprioritize reply-chain chunks vs standalone comments.
        "is_thread": bool(chunk.get("is_thread")),
        # JSON-encoded since Chroma metadata values must be scalars. Lets a
        # prereq check walk the actual and/or tree exactly, instead of
        # trusting an LLM to parse boolean logic out of embedded prose.
        "prereq_tree": json.dumps(prereq_tree) if prereq_tree else "",
        # Only set on "programme" chunks (see chunk.py's build_programme_chunks) -
        # retriever.py filters on programme_code the same way it filters
        # review/info chunks on course_code.
        "programme_code": chunk.get("programme_code") or "",
        "section_title": chunk.get("section_title") or "",
    }


def embed_and_upsert(chunks: list[dict] | None = None):
    if chunks is None:
        chunks = load_chunks()
    if not chunks:
        print("No chunks to embed.")
        return

    collection = get_collection()

    current_ids = {c["id"] for c in chunks}
    existing = collection.get(ids=None, include=["documents"])
    existing_ids = set(existing["ids"])
    existing_text_by_id = dict(zip(existing["ids"], existing["documents"]))

    stale_ids = existing_ids - current_ids
    if stale_ids:
        collection.delete(ids=list(stale_ids))
        print(f"deleted {len(stale_ids)} stale vector(s) no longer in chunks.jsonl")

    # Skip the (paid, rate-limited) OpenAI call for any chunk whose text is
    # byte-identical to what's already stored - only new or actually-changed
    # chunks need a fresh embedding. Without this, re-running embed over a
    # chunks.jsonl that still contains every existing chunk verbatim - e.g.
    # chunk.py's --programme-only, which rebuilds only programme chunks but
    # leaves the (possibly catalog-sized) course chunks in place unchanged -
    # would re-embed the entire collection every time regardless.
    to_embed = [c for c in chunks if existing_text_by_id.get(c["id"]) != c["text"]]
    skipped = len(chunks) - len(to_embed)
    if skipped:
        print(f"skipping {skipped} chunk(s) with unchanged text (already embedded)")

    for i in range(0, len(to_embed), BATCH_SIZE):
        batch = to_embed[i:i + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        ids = [c["id"] for c in batch]
        metadatas = [chunk_metadata(c) for c in batch]

        embeddings = embed_texts(texts)

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        print(f"upserted {min(i + BATCH_SIZE, len(to_embed))}/{len(to_embed)} chunks")

    print(f"Done. Collection '{COLLECTION_NAME}' now has {collection.count()} vectors.")


if __name__ == "__main__":
    embed_and_upsert()
