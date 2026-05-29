"""
seed_policies.py — Chunk, embed, and insert compliance policies into the DB.

Usage:
    cd ~/Desktop/Financial_Plan_AI
    export DATABASE_URL="postgresql://..."
    python3 scripts/seed_policies.py

Embeddings are generated locally via sentence-transformers (all-MiniLM-L6-v2),
no Ollama or external API required.
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
    """
    Generate TF-IDF style embeddings using pure Python stdlib — no ML libs needed.
    Produces 384-dim normalised vectors good enough for policy retrieval.
    """
    import hashlib
    import math
    import re

    DIM = 384

    def tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z]+", text.lower())

    texts = [chunk["content"] for chunk in chunks]
    total = len(texts)

    print("\nGenerating embeddings (pure-Python TF-IDF, no ML libs needed)...", flush=True)

    # Build IDF from corpus
    tokenized = [tokenize(t) for t in texts]
    df: dict[str, int] = {}
    for tokens in tokenized:
        for word in set(tokens):
            df[word] = df.get(word, 0) + 1

    N = len(texts)
    idf = {w: math.log((N + 1) / (freq + 1)) + 1 for w, freq in df.items()}

    def embed(tokens: list[str]) -> list[float]:
        # Map each word to a bucket in DIM-space via hash, weight by TF-IDF
        vec = [0.0] * DIM
        freq: dict[str, int] = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        for word, count in freq.items():
            tf = count / max(len(tokens), 1)
            weight = tf * idf.get(word, 1.0)
            # Deterministic bucket via SHA-256
            idx = int(hashlib.sha256(word.encode()).hexdigest(), 16) % DIM
            vec[idx] += weight
        # L2 normalise
        mag = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / mag for x in vec]

    vectors = []
    for i, tokens in enumerate(tokenized, 1):
        print(f"  [{i}/{total}] {chunks[i-1]['title'][:60]}", flush=True)
        vectors.append(embed(tokens))

    print(f"\n  ✓ {total} embeddings generated (dim={DIM})", flush=True)
    return vectors


async def insert_into_db(dsn: str, chunks: list[dict], embeddings: list[list[float]]) -> None:
    """Async step — insert chunks + embeddings into the policies table."""
    print("\nInserting into database...", flush=True)

    # Strip sslmode from DSN — asyncpg handles it via ssl= parameter
    ssl = None
    clean_dsn = dsn
    if "sslmode=require" in dsn:
        ssl = "require"
        clean_dsn = dsn.replace("?sslmode=require", "").replace("&sslmode=require", "").replace("sslmode=require", "")

    conn = await asyncpg.connect(clean_dsn, ssl=ssl)

    try:
        # Clear old policies so this script is idempotent
        deleted = await conn.fetchval("DELETE FROM policies RETURNING id")
        print("  Cleared existing policy chunks", flush=True)

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

        # Quick similarity test using same pure-Python embedder
        print("\nSimilarity test:", flush=True)
        import hashlib
        import math
        import re
        DIM = 384
        query = "transaction exceeding ten thousand dollars reporting"
        tokens = re.findall(r"[a-z]+", query.lower())
        vec = [0.0] * DIM
        for word in tokens:
            idx = int(hashlib.sha256(word.encode()).hexdigest(), 16) % DIM
            vec[idx] += 1.0
        mag = math.sqrt(sum(x*x for x in vec)) or 1.0
        q_emb = [x / mag for x in vec]

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
        print("ERROR: DATABASE_URL not set. Run:")
        print('  export DATABASE_URL="postgresql://..."')
        sys.exit(1)

    # Step 1: chunk (sync)
    chunks = chunk_all_policies()

    # Step 2: embed locally (sync)
    embeddings = generate_embeddings(chunks)

    # Step 3: insert (async)
    asyncio.run(insert_into_db(dsn, chunks, embeddings))
