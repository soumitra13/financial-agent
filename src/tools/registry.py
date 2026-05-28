"""
Tool registry — central list of tools the agent can call.

Each tool has:
  - name: matches the function name the LLM will emit
  - description: what the LLM sees when deciding which tool to call
  - parameters: JSON Schema for the arguments
  - handler: the async Python function that executes it
  - category: "read" or "write" (used by guardrails)
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from src.tools.transactions import get_account_transactions, get_account_profile, search_similar_transactions
from src.tools.anomaly import flag_anomaly
from src.tools.customer import draft_customer_explanation
from src.tools.policy import check_policy_compliance


# ── Tool definitions (sent to the LLM) ───────────────────────────────────────

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_account_transactions",
        "description": "Retrieve recent transactions for an account within a date range.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Account UUID"},
                "days_back": {"type": "integer", "default": 90, "description": "How many days back to look (default 90)"},
                "min_amount": {"type": "number", "description": "Optional minimum transaction amount filter"},
            },
            "required": ["account_id"],
        },
        "category": "read",
    },
    {
        "name": "get_account_profile",
        "description": "Get account holder profile, account type, status, and risk score.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Account UUID"},
            },
            "required": ["account_id"],
        },
        "category": "read",
    },
    {
        "name": "search_similar_transactions",
        "description": "Find transactions with similar amounts or patterns across all accounts.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount_range": {"type": "string", "description": "Amount range e.g. '9000-10000'"},
                "time_window_hours": {"type": "integer", "description": "Look-back window in hours"},
                "category": {"type": "string", "description": "Optional transaction category filter"},
            },
            "required": ["amount_range"],
        },
        "category": "read",
    },
    # flag_anomaly is intentionally NOT exposed to the LLM.
    # Anomaly detection is handled by the Python rules engine (pre_analyzer.py),
    # which guarantees real transaction UUIDs. The LLM cannot reliably extract
    # UUIDs from raw data and will hallucinate them if given this tool.
    {
        "name": "check_policy_compliance",
        "description": "Check which compliance policies apply to a transaction or pattern. Uses semantic search over policy documents.",
        "parameters": {
            "type": "object",
            "properties": {
                "transaction_details": {
                    "type": "string",
                    "description": "Natural language description of the transaction or pattern to check",
                },
            },
            "required": ["transaction_details"],
        },
        "category": "read",
    },
    {
        "name": "draft_customer_explanation",
        "description": "Draft a professional customer-facing explanation for a flagged transaction.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "flagged_transactions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of flagged transaction IDs",
                },
                "tone": {"type": "string", "default": "professional"},
            },
            "required": ["account_id", "flagged_transactions"],
        },
        "category": "write",
    },
]

# ── Handler map ───────────────────────────────────────────────────────────────

TOOL_HANDLERS: dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {
    "get_account_transactions": get_account_transactions,
    "get_account_profile": get_account_profile,
    "search_similar_transactions": search_similar_transactions,
    "flag_anomaly": flag_anomaly,
    "check_policy_compliance": check_policy_compliance,
    "draft_customer_explanation": draft_customer_explanation,
}

ALLOWED_TOOLS: set[str] = set(TOOL_HANDLERS.keys())


async def execute_tool(name: str, arguments: dict[str, Any]) -> Any:
    """
    Dispatch a tool call by name.
    Raises ValueError if the tool is not in the allowlist.
    """
    if name not in ALLOWED_TOOLS:
        raise ValueError(f"Tool '{name}' is not registered. Allowed: {sorted(ALLOWED_TOOLS)}")
    handler = TOOL_HANDLERS[name]
    return await handler(**arguments)
