"""
embed.py

Embeds chunks from data/chunks/chunks.jsonl (see chunk.py) using a local
sentence-transformers model and upserts them into a persistent local Chroma
collection. Upserts are keyed by chunk id, so re-running this after a
re-chunk is idempotent (no duplicate vectors). Any id present in the
collection but no longer in chunks.jsonl (e.g. a course produced fewer
chunks on re-chunk, so its old high-index ids no longer exist) is deleted
first, so stale vectors never linger and get returned by retrieval.

USAGE
-----
python embed.py
"""

from __future__ import annotations

import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

BACKEND_DIR = Path(__file__).resolve().parents[2]
CHUNKS_PATH = BACKEND_DIR / "data" / "chunks" / "chunks.jsonl"
CHROMA_DIR = BACKEND_DIR / "data" / "chroma_db"
COLLECTION_NAME = "nusmods_reviews"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
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
    }


def embed_and_upsert(chunks: list[dict] | None = None):
    if chunks is None:
        chunks = load_chunks()
    if not chunks:
        print("No chunks to embed.")
        return

    model = SentenceTransformer(EMBEDDING_MODEL)
    collection = get_collection()

    current_ids = {c["id"] for c in chunks}
    existing_ids = set(collection.get(ids=None)["ids"])
    stale_ids = existing_ids - current_ids
    if stale_ids:
        collection.delete(ids=list(stale_ids))
        print(f"deleted {len(stale_ids)} stale vector(s) no longer in chunks.jsonl")

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        ids = [c["id"] for c in batch]
        metadatas = [chunk_metadata(c) for c in batch]

        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        print(f"upserted {min(i + BATCH_SIZE, len(chunks))}/{len(chunks)} chunks")

    print(f"Done. Collection '{COLLECTION_NAME}' now has {collection.count()} vectors.")


if __name__ == "__main__":
    embed_and_upsert()
