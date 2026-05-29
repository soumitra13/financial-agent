"""
pre_analyzer.py — Rules-based transaction analysis run before the LLM loop.

Why: Small models (llama3.2:3b) cannot reliably extract UUIDs from raw JSON
and use them in structured output. Instead, we detect anomalies in Python,
then inject a pre-built findings summary into the agent's context. The LLM
only needs to write the narrative — it never needs to parse raw data.

Rules implemented:
  - Structuring  : amount between $8,000–$9,999
  - Velocity     : more than 5 transactions within any 24-hour window
  - Geographic   : transfer to a high-risk country code
  - Large amount : single transaction > 3× the account's median
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

HIGH_RISK_COUNTRIES = {"NG", "IR", "KP", "SY", "CU", "MM", "BY"}
STRUCTURING_LOW  = 8_000
STRUCTURING_HIGH = 9_999
VELOCITY_WINDOW_HOURS = 24
VELOCITY_THRESHOLD = 5
LARGE_AMOUNT_MULTIPLIER = 3.0


def analyze_transactions(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Run all rules against a list of transaction dicts.
    Returns a list of finding dicts, each with a guaranteed real transaction_id.
    """
    if not transactions:
        return []

    findings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()   # deduplicate per transaction

    amounts = [float(t.get("amount", 0)) for t in transactions if t.get("amount")]
    med = median(amounts) if amounts else 0

    # Index by timestamp for velocity check
    by_time: list[tuple[datetime, str, dict]] = []
    for tx in transactions:
        ts_raw = tx.get("created_at") or tx.get("timestamp") or tx.get("date")
        tx_id = str(tx.get("id") or tx.get("transaction_id") or "")
        if not tx_id:
            continue
        try:
            if isinstance(ts_raw, str):
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            elif isinstance(ts_raw, datetime):
                ts = ts_raw if ts_raw.tzinfo else ts_raw.replace(tzinfo=UTC)
            else:
                ts = None
        except (ValueError, TypeError):
            ts = None
        by_time.append((ts, tx_id, tx))

    for ts, tx_id, tx in by_time:
        amount = float(tx.get("amount", 0))
        # DB schema: country_code (ISO 3166-1 alpha-2); fallbacks for tool aliases
        country = (tx.get("country_code") or
                   tx.get("destination_country") or
                   tx.get("merchant_country") or
                   tx.get("country") or "")

        # ── Structuring ────────────────────────────────────────────────────────
        if STRUCTURING_LOW <= amount <= STRUCTURING_HIGH and tx_id not in seen_ids:
            findings.append({
                "transaction_id": tx_id,
                "anomaly_type": "structuring",
                "severity": "high",
                "evidence": (
                    f"Amount ${amount:,.2f} falls in the ${STRUCTURING_LOW:,}–"
                    f"${STRUCTURING_HIGH:,} range, consistent with structuring to "
                    f"avoid the $10,000 CTR reporting threshold."
                ),
                "policy_reference": "AML Thresholds Policy — Structuring Detection",
            })
            seen_ids.add(tx_id)

        # ── Geographic risk ────────────────────────────────────────────────────
        if country.upper() in HIGH_RISK_COUNTRIES and tx_id not in seen_ids:
            findings.append({
                "transaction_id": tx_id,
                "anomaly_type": "geographic",
                "severity": "high",
                "evidence": (
                    f"Transfer of ${amount:,.2f} to high-risk country '{country}'. "
                    f"This jurisdiction is subject to enhanced due diligence."
                ),
                "policy_reference": "Geographic Risk Policy",
            })
            seen_ids.add(tx_id)

        # ── Large amount ───────────────────────────────────────────────────────
        if med > 0 and amount > LARGE_AMOUNT_MULTIPLIER * med and tx_id not in seen_ids:
            findings.append({
                "transaction_id": tx_id,
                "anomaly_type": "amount",
                "severity": "medium",
                "evidence": (
                    f"Transaction of ${amount:,.2f} is "
                    f"{amount / med:.1f}× the account median (${med:,.2f}), "
                    f"which is significantly out of pattern."
                ),
                "policy_reference": "AML Thresholds Policy — Large Transaction",
            })
            seen_ids.add(tx_id)

    # ── Velocity ───────────────────────────────────────────────────────────────
    timed = [(ts, tx_id, tx) for ts, tx_id, tx in by_time if ts is not None]
    timed.sort(key=lambda x: x[0])

    for i, (ts_i, tx_id_i, tx_i) in enumerate(timed):
        window = [tx_id_i]
        for j in range(i + 1, len(timed)):
            ts_j, tx_id_j, _ = timed[j]
            if (ts_j - ts_i) <= timedelta(hours=VELOCITY_WINDOW_HOURS):
                window.append(tx_id_j)
            else:
                break
        if len(window) > VELOCITY_THRESHOLD and tx_id_i not in seen_ids:
            findings.append({
                "transaction_id": tx_id_i,
                "anomaly_type": "velocity",
                "severity": "medium",
                "evidence": (
                    f"{len(window)} transactions detected within a 24-hour window "
                    f"starting at {ts_i.isoformat()}, exceeding the threshold of "
                    f"{VELOCITY_THRESHOLD}."
                ),
                "policy_reference": "Velocity Checks Policy",
            })
            seen_ids.add(tx_id_i)

    return findings


def build_findings_context(
    account_id: str,
    transactions: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> str:
    """
    Build a plain-text context block injected into the agent's user message.
    The LLM reads this and writes the narrative — it never touches raw JSON.
    """
    lines = [
        f"PRE-ANALYSIS RESULTS FOR ACCOUNT {account_id}",
        f"Transactions reviewed: {len(transactions)}",
        f"Anomalies detected: {len(findings)}",
        "",
    ]

    if not findings:
        lines.append("No anomalies detected. Account activity appears normal.")
    else:
        lines.append("FLAGGED TRANSACTIONS (use these exact IDs and details in your answer):")
        for i, f in enumerate(findings, 1):
            lines.append(
                f"\n  [{i}] transaction_id : {f['transaction_id']}"
                f"\n      anomaly_type   : {f['anomaly_type']}"
                f"\n      severity       : {f['severity']}"
                f"\n      evidence       : {f['evidence']}"
                f"\n      policy         : {f['policy_reference']}"
            )

    lines += [
        "",
        "Using the findings above, write your final JSON answer.",
        "Copy transaction_ids EXACTLY as shown — do not modify or invent them.",
    ]

    return "\n".join(lines)
