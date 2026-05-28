"""
mock.py — Deterministic LLM adapter for pipeline testing.

Simulates a realistic agent that:
  Step 1 → calls get_account_transactions
  Step 2 → calls check_policy_compliance
  Step 3 → calls flag_anomaly (if suspicious tx found)
  Step 4 → returns structured JSON final answer

No network calls, no Ollama, instant responses.
Set LLM_PROVIDER=mock in .env to use.
"""

from __future__ import annotations

import json
import re
from typing import Any

from src.llm.adapter import LLMResponse, ToolCall


class MockAdapter:
    """
    Stateful mock that advances through a scripted multi-step agent flow.
    State is tracked per-instance (one instance per agent run).
    """

    def __init__(self) -> None:
        self._step = 0
        self._transactions: list[dict] = []
        self._account_id: str = ""
        self._flagged: list[dict] = []

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self._step += 1

        # Extract account_id from first user message if not set
        if not self._account_id:
            user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")
            match = re.search(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                user_msg,
            )
            if match:
                self._account_id = match.group()

        # Parse tool results from previous steps
        tool_results = [m for m in messages if m.get("role") == "tool"]
        if tool_results:
            last_result = tool_results[-1].get("content", "")
            try:
                parsed = json.loads(last_result)
                if isinstance(parsed, list) and parsed and "amount" in str(parsed[0]):
                    self._transactions = parsed[:20]  # keep first 20
                    # Find suspicious ones: amounts 9000-9999 (structuring pattern)
                    self._flagged = [
                        t for t in self._transactions
                        if isinstance(t.get("amount"), (int, float))
                        and 8900 <= float(t["amount"]) <= 9999
                    ]
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        # ── Step 1: fetch transactions ────────────────────────────────────────
        if self._step == 1:
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(
                    name="get_account_transactions",
                    arguments={"account_id": self._account_id, "days_back": 30},
                    call_id="mock-1",
                )],
            )

        # ── Step 2: check policy compliance ──────────────────────────────────
        if self._step == 2:
            n = len(self._flagged)
            detail = (
                f"{n} transactions between $8,900 and $9,999 detected — potential structuring"
                if n > 0
                else "Multiple transactions reviewed, checking AML thresholds"
            )
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(
                    name="check_policy_compliance",
                    arguments={"transaction_details": detail},
                    call_id="mock-2",
                )],
            )

        # ── Step 3: flag anomalies ────────────────────────────────────────────
        if self._step == 3 and self._flagged:
            tx = self._flagged[0]
            tx_id = tx.get("id") or tx.get("transaction_id", "unknown")
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(
                    name="flag_anomaly",
                    arguments={
                        "transaction_id": str(tx_id),
                        "anomaly_type": "structuring",
                        "severity": "high",
                        "evidence": (
                            f"Transaction of ${tx.get('amount')} is just below the $10,000 "
                            f"reporting threshold. Pattern consistent with structuring. "
                            f"Found {len(self._flagged)} similar transactions this period."
                        ),
                        "policy_reference": "AML Thresholds Policy",
                    },
                    call_id="mock-3",
                )],
            )

        # ── Final answer ──────────────────────────────────────────────────────
        n_flagged = len(self._flagged)
        has_anomalies = n_flagged > 0

        result = {
            "summary": (
                f"Analysis complete for account {self._account_id}. "
                f"Reviewed {len(self._transactions)} recent transactions. "
                + (
                    f"Identified {n_flagged} transaction(s) consistent with structuring — "
                    f"amounts between $8,900–$9,999 appearing to evade the $10,000 CTR threshold."
                    if has_anomalies
                    else "No suspicious patterns detected in the review period."
                )
            ),
            "anomalies_found": [
                {
                    "transaction_id": str(t.get("id") or t.get("transaction_id", "unknown")),
                    "anomaly_type": "structuring",
                    "severity": "high",
                    "evidence": f"Amount ${t.get('amount')} just below $10,000 reporting threshold",
                    "policy_reference": "AML Thresholds Policy — Section 3.1",
                }
                for t in self._flagged[:3]
            ],
            "policies_checked": ["AML Thresholds Policy", "Structuring Detection Policy"],
            "recommendation": (
                "File a Suspicious Activity Report (SAR) and escalate to compliance team for review."
                if has_anomalies
                else "No action required. Continue standard monitoring."
            ),
            "requires_escalation": has_anomalies,
            "escalation_reason": (
                f"{n_flagged} structuring transaction(s) identified — SAR filing may be required."
                if has_anomalies
                else None
            ),
        }

        return LLMResponse(content=json.dumps(result), tool_calls=[])
