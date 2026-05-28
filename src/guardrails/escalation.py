"""
escalation.py — Auto-escalate critical anomaly findings.

When the validated AgentOutput has requires_escalation=True, this module
inserts a record into the escalations table so the compliance team can action it.

The escalations table schema (from init.sql):
    id             UUID PRIMARY KEY
    task_id        UUID REFERENCES tasks(id)
    account_id     UUID REFERENCES accounts(id)  -- nullable
    reason         TEXT
    severity       TEXT
    status         TEXT DEFAULT 'open'
    reviewed_by    TEXT
    reviewed_at    TIMESTAMPTZ
    created_at     TIMESTAMPTZ DEFAULT NOW()
"""

from __future__ import annotations

from uuid import UUID

from src.db.connection import get_connection
from src.guardrails.output_validator import AgentOutput


async def maybe_escalate(
    task_id: UUID,
    output: AgentOutput,
    account_id: str | None = None,   # kept for signature compat, not stored
) -> UUID | None:
    """
    If the validated output requires escalation, insert an escalation record.

    Returns the new escalation UUID, or None if no escalation was needed.
    """
    if not output.requires_escalation:
        return None

    # Determine highest severity present
    severity_order = ["critical", "high", "medium", "low"]
    severities = [a.severity for a in output.anomalies_found]
    top_severity = next(
        (s for s in severity_order if s in severities),
        "high",
    )

    reason = output.escalation_reason or (
        f"Agent flagged {len(output.anomalies_found)} anomaly/ies "
        f"requiring compliance review. "
        f"Recommendation: {output.recommendation}"
    )

    # agent_analysis: store the full anomaly list as JSONB for the reviewer
    import json
    agent_analysis = {
        "anomalies": [a.model_dump() for a in output.anomalies_found],
        "policies_checked": output.policies_checked,
        "recommendation": output.recommendation,
    }

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO escalations (task_id, reason, agent_analysis, severity, status)
            VALUES ($1, $2, $3::jsonb, $4, 'pending')
            RETURNING id
            """,
            task_id,
            reason,
            json.dumps(agent_analysis),
            top_severity,
        )

    escalation_id = row["id"]
    print(f"  🚨 Escalation created: {escalation_id} (severity={top_severity})")
    return escalation_id
