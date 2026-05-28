"""
seed_policies.py — Chunk, embed, and insert compliance policies into the DB.

Usage:
    cd ~/Desktop/Financial_Plan_AI
    python3 scripts/seed_policies.py

Embedding happens synchronously (outside asyncio) to avoid httpx/asyncio
conflicts on Python 3.14. DB insertion is then done via asyncpg.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import asyncpg


def chunk_all_policies() -> list[dict]:
    """Pure sync step — read and chunk all policy markdown files."""
    from src.rag.chunker import chunk_markdown_file

    policies_dir = Path(__file__).parent.parent / "config" / "policies"
    md_files = sorted(policies_dir.glob("*.md"))

    if not md_files:
        print(f"ERROR: No markdown files found in {policies_dir}")
        sys.exit(1)

    print(f"Found {len(md_files)} policy files:", flush=True)
    for f in md_files:
        print(f"  - {f.name}", flush=True)

    all_chunks = []
    for filepath in md_files:
        chunks = chunk_markdown_file(str(filepath))
        all_chunks.extend(chunks)
        print(f"  {filepath.name}: {len(chunks)} chunks", flush=True)

    print(f"\nTotal chunks: {len(all_chunks)}", flush=True)
    return all_chunks


def generate_embeddings(chunks: list[dict]) -> list[list[float]]:
    """Pure sync step — call Ollama for each chunk embedding."""
    import httpx

    # Use OLLAMA_BASE_URL env var so this works both locally and inside Docker
    # (Docker: host.docker.internal:11434, local: localhost:11434)
    ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    embed_url = f"{ollama_base}/api/embeddings"

    print("\nGenerating embeddings via Ollama (all-minilm)...", flush=True)
    print(f"  Ollama URL: {embed_url}", flush=True)
    print("  First call may take 20-30s while model loads\n", flush=True)

    embeddings = []
    total = len(chunks)

    for i, chunk in enumerate(chunks, 1):
        print(f"  [{i}/{total}] {chunk['title'][:60]}", flush=True)
        response = httpx.post(
            embed_url,
            json={"model": "all-minilm", "prompt": chunk["content"]},
            timeout=60.0,
        )
        response.raise_for_status()
        embeddings.append(response.json()["embedding"])

    print(f"\n  ✓ {total} embeddings generated", flush=True)
    return embeddings


async def insert_into_db(dsn: str, chunks: list[dict], embeddings: list[list[float]]) -> None:
    """Async step — insert chunks + embeddings into the policies table."""
    print("\nInserting into database...", flush=True)
    conn = await asyncpg.connect(dsn)

    try:
        await conn.execute("DELETE FROM policies")
        print("  Cleared existing policies", flush=True)

        await conn.set_type_codec(
            "vector",
            encoder=lambda v: "[" + ",".join(str(x) for x in v) + "]",
            decoder=lambda v: [float(x) for x in v.strip("[]").split(",")],
            schema="public",
            format="text",
        )

        for chunk, embedding in zip(chunks, embeddings):
            await conn.execute(
                """
                INSERT INTO policies (title, content, category, embedding)
                VALUES ($1, $2, $3, $4::vector)
                """,
                chunk["title"],
                chunk["content"],
                chunk["category"],
                embedding,
            )

        total = await conn.fetchval("SELECT COUNT(*) FROM policies")
        print(f"\n✅ Done! {total} policy chunks in DB with embeddings.", flush=True)

        # Similarity test
        print("\nSimilarity test:", flush=True)
        import httpx
        ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        r = httpx.post(
            f"{ollama_base}/api/embeddings",
            json={"model": "all-minilm", "prompt": "transaction exceeding ten thousand dollars reporting"},
            timeout=30.0,
        )
        q_emb = r.json()["embedding"]
        rows = await conn.fetch(
            """
            SELECT title, 1 - (embedding <=> $1::vector) AS similarity
            FROM policies ORDER BY embedding <=> $1::vector LIMIT 3
            """,
            q_emb,
        )
        for row in rows:
            print(f"  [{row['similarity']:.3f}] {row['title']}", flush=True)

    finally:
        await conn.close()


if __name__ == "__main__":
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL not set.")
        sys.exit(1)

    # Step 1: chunk (sync)
    chunks = chunk_all_policies()

    # Step 2: embed (sync — avoids httpx/asyncio conflict on Python 3.14)
    embeddings = generate_embeddings(chunks)

    # Step 3: insert (async)
    asyncio.run(insert_into_db(dsn, chunks, embeddings))
