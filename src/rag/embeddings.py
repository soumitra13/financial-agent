"""
embeddings.py — Generate embeddings using Ollama's local embedding API.

Model: all-minilm (384 dimensions, matches policies.embedding vector(384))
Requires: ollama pull all-minilm

No PyTorch or ONNX needed — uses the same Ollama server already running.
"""

from __future__ import annotations

import httpx

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "all-minilm"
DIMENSIONS = 384


def embed_text(text: str) -> list[float]:
    """Generate a 384-dimensional embedding for a single text string."""
    response = httpx.post(
        OLLAMA_EMBED_URL,
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts, one request each."""
    embeddings = []
    total = len(texts)
    for i, text in enumerate(texts, 1):
        if i == 1 or i % 5 == 0 or i == total:
            print(f"  Embedding {i}/{total}...", flush=True)
        embeddings.append(embed_text(text))
    return embeddings
