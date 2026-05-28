"""Stub tool for drafting customer-facing explanations."""

from __future__ import annotations

from typing import Any


async def draft_customer_explanation(
    account_id: str,
    flagged_transactions: list[str],
    tone: str = "professional",
) -> dict[str, Any]:
    """
    Stub: drafts a customer explanation for flagged transactions.
    Phase 2 will use the LLM to generate a real explanation.
    """
    txn_list = ", ".join(flagged_transactions[:3])
    return {
        "account_id": account_id,
        "tone": tone,
        "requires_review": True,
        "subject": "Important notice regarding your recent account activity",
        "body": (
            f"Dear Valued Customer,\n\n"
            f"We are writing to inform you that we have identified activity on your account "
            f"that requires your attention. Specifically, transactions {txn_list} have been "
            f"flagged for review by our compliance team.\n\n"
            f"Please contact us at 1-800-XXX-XXXX if you have any questions.\n\n"
            f"Sincerely,\nCompliance Team"
        ),
        "flagged_transactions": flagged_transactions,
    }
