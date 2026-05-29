"""
output_validator.py — Pydantic schema for the agent's final answer.

The agent is instructed (via system prompt) to return a JSON blob.
This module validates and coerces that blob so we always store a
well-typed object in the DB — never raw LLM text.

Schema:
  AgentOutput
    summary              : str           — one-paragraph human-readable summary
    anomalies_found      : list[Anomaly] — each flagged transaction
    policies_checked     : list[str]     — policy names consulted
    recommendation       : str           — what the compliance team should do
    requires_escalation  : bool          — true if any anomaly is critical
    escalation_reason    : str | None    — why escalation is needed
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Sub-models ────────────────────────────────────────────────────────────────

class AnomalyRecord(BaseModel):
    transaction_id: str
    anomaly_type: str
    severity: Literal["low", "medium", "high", "critical"]
    evidence: str
    policy_reference: str | None = None


# ── Top-level output model ────────────────────────────────────────────────────

class AgentOutput(BaseModel):
    summary: str = Field(..., min_length=10)
    anomalies_found: list[AnomalyRecord] = Field(default_factory=list)
    policies_checked: list[str] = Field(default_factory=list)
    recommendation: str = Field(default="No action required.")
    requires_escalation: bool = False
    escalation_reason: str | None = None

    @model_validator(mode="after")
    def _sync_escalation_flag(self) -> AgentOutput:
        """Auto-set requires_escalation=True if any anomaly is critical."""
        has_critical = any(a.severity == "critical" for a in self.anomalies_found)
        if has_critical and not self.requires_escalation:
            self.requires_escalation = True
            if not self.escalation_reason:
                self.escalation_reason = "Critical anomaly detected — requires human review."
        return self

    @field_validator("anomalies_found", mode="before")
    @classmethod
    def _coerce_anomalies(cls, v: Any) -> list[dict]:
        """Accept a list of dicts or a single dict wrapped in a list."""
        if isinstance(v, dict):
            return [v]
        return v or []

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


# ── Validation helper ─────────────────────────────────────────────────────────

def validate_output(raw: dict[str, Any] | str) -> AgentOutput:
    """
    Parse and validate the agent's raw output.

    Accepts:
      - a dict  (already parsed JSON)
      - a str   (raw LLM text — tries to extract JSON block first)

    Returns a validated AgentOutput.
    Raises ValidationError (Pydantic) if it cannot be coerced.
    Falls back to a minimal valid output if the agent returned plain text.
    """
    if isinstance(raw, str):
        # Try to extract a JSON block
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                raw = json.loads(match.group())
            except json.JSONDecodeError:
                # Return a minimal valid output from the plain text
                return AgentOutput(
                    summary=raw[:500] or "Agent returned unstructured output.",
                    recommendation="Manual review required — output was not structured JSON.",
                )
        else:
            return AgentOutput(
                summary=raw[:500] or "Agent returned unstructured output.",
                recommendation="Manual review required — output was not structured JSON.",
            )

    # Ensure summary exists (some models omit it)
    if isinstance(raw, dict) and "summary" not in raw:
        raw["summary"] = raw.get("recommendation", "No summary provided by agent.")

    return AgentOutput.model_validate(raw)
