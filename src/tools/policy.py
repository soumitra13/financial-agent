"""
Policy compliance tool — RAG over compliance policy documents.
"""

from __future__ import annotations

from typing import Any


async def check_policy_compliance(
    transaction_details: str = "",
    description: str = "",       # alias — model sometimes uses this name
    query: str = "",             # alias — model sometimes uses this name
) -> dict[str, Any]:
    """
    Given a description of a transaction or pattern, retrieve the most
    relevant compliance policy chunks via vector similarity search.
    Accepts transaction_details, description, or query as the input parameter.
    """
    from src.rag.retriever import retrieve_policies

    # Accept whichever parameter name the model chose to use
    text = transaction_details or description or query or "general compliance check"
    results = await retrieve_policies(text, top_k=3)

    if not results:
        return {
            "query": text,
            "policies_found": 0,
            "policies": [],
            "summary": "No relevant policies found.",
        }

    return {
        "query": text,
        "policies_found": len(results),
        "policies": results,
        "summary": f"Found {len(results)} relevant policy sections.",
    }
