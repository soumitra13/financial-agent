"""
Real DB-backed tool for flagging anomalous transactions.
Updates the transactions table and writes to audit_log.
"""

from __future__ import annotations

from typing import Any

from src.db.connection import get_connection


async def flag_anomaly(
    transaction_id: str,
    anomaly_type: str,
    severity: str,
    evidence: str,
    policy_reference: str | None = None,
) -> dict[str, Any]:
    """
    Flag a transaction as anomalous in the DB.
    Updates is_flagged + flag_reason on the transactions table.
    """
    if not transaction_id or not anomaly_type or not severity or not evidence:
        return {"error": "transaction_id, anomaly_type, severity, and evidence are all required"}

    reason = f"[{anomaly_type.upper()}:{severity.upper()}] {evidence}"
    if policy_reference:
        reason += f" | Policy: {policy_reference}"

    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE transactions
            SET is_flagged = TRUE, flag_reason = $1
            WHERE id = $2::uuid
            """,
            reason,
            transaction_id,
        )

    rows_updated = int(result.split()[-1]) if result else 0

    if rows_updated == 0:
        return {"error": f"Transaction {transaction_id} not found"}

    print(f"  [FLAG] {transaction_id[:8]}... | {anomaly_type} | {severity}")

    return {
        "success": True,
        "transaction_id": transaction_id,
        "anomaly_type": anomaly_type,
        "severity": severity,
        "evidence": evidence,
        "policy_reference": policy_reference,
        "message": f"Transaction flagged as {anomaly_type} ({severity})",
    }
