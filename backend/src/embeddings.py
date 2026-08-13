"""
embeddings.py

Shared OpenAI embedding client for embed.py (indexing) and retriever.py
(query time). Both MUST use the exact same model - index-time and
query-time vectors have to live in the same embedding space, or retrieval
distances are meaningless.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

EMBEDDING_MODEL = "text-embedding-3-small"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Add it to backend/.env or the environment."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts, preserving input order."""
    if not texts:
        return []
    client = _get_client()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]
