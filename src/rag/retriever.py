"""
retriever.py — Vector similarity search over compliance policies.

Given a query string, embed it and find the top-k most similar
policy chunks using pgvector cosine similarity.
"""

from __future__ import annotations

from src.db.connection import get_connection
from src.rag.embeddings import embed_text

DEFAULT_TOP_K = 3


async def retrieve_policies(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """
    Find the most relevant compliance policy chunks for a given query.

    Parameters
    ----------
    query:   Natural language description of the transaction or pattern
    top_k:   Number of chunks to return

    Returns
    -------
    List of dicts with: title, content, category, similarity
    """
    query_embedding = embed_text(query)

    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                title,
                content,
                category,
                1 - (embedding <=> $1::vector) AS similarity
            FROM policies
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            query_embedding,
            top_k,
        )

    return [
        {
            "title": row["title"],
            "content": row["content"],
            "category": row["category"],
            "similarity": round(float(row["similarity"]), 4),
        }
        for row in rows
    ]


async def retrieve_policies_for_transaction(
    amount: float,
    country_code: str,
    category: str,
    direction: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """
    Convenience wrapper that builds a natural language query
    from transaction attributes and retrieves relevant policies.
    """
    query = (
        f"A {direction} transaction of ${amount:.2f} "
        f"categorized as {category} "
        f"involving country {country_code}."
    )
    return await retrieve_policies(query, top_k=top_k)
