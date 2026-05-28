"""
Real SQL-backed tool implementations for transactions.
Replaces the Phase 1 stubs.
"""

from __future__ import annotations

from typing import Any

from src.db.connection import get_connection


async def get_account_transactions(
    account_id: str,
    days_back: int = 90,
    min_amount: float | None = None,
) -> dict[str, Any]:
    """Query real transactions from the DB for the given account."""
    async with get_connection() as conn:
        # Verify account exists
        account = await conn.fetchrow(
            "SELECT id, customer_name, account_type, risk_score FROM accounts WHERE id = $1",
            account_id,
        )
        if not account:
            return {"error": f"Account {account_id} not found"}

        query = """
            SELECT id, amount, currency, direction, counterparty,
                   category, country_code, is_flagged, flag_reason, created_at
            FROM transactions
            WHERE account_id = $1
              AND created_at >= NOW() - ($2 || ' days')::INTERVAL
        """
        params: list[Any] = [account_id, str(days_back)]

        if min_amount is not None:
            query += " AND amount >= $3"
            params.append(min_amount)

        query += " ORDER BY created_at DESC LIMIT 100"

        rows = await conn.fetch(query, *params)

    transactions = [
        {
            "id": str(r["id"]),
            "amount": float(r["amount"]),
            "currency": r["currency"],
            "direction": r["direction"],
            "counterparty": r["counterparty"],
            "category": r["category"],
            "country_code": r["country_code"],
            "is_flagged": r["is_flagged"],
            "flag_reason": r["flag_reason"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]

    return {
        "account_id": account_id,
        "customer_name": account["customer_name"],
        "risk_score": float(account["risk_score"]),
        "days_back": days_back,
        "count": len(transactions),
        "transactions": transactions,
    }


async def get_account_profile(account_id: str) -> dict[str, Any]:
    """Fetch real account profile and compute 90-day average transaction amount."""
    async with get_connection() as conn:
        account = await conn.fetchrow(
            """
            SELECT id, customer_name, account_type, status, risk_score, created_at
            FROM accounts WHERE id = $1
            """,
            account_id,
        )
        if not account:
            return {"error": f"Account {account_id} not found"}

        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*)                  AS txn_count,
                COALESCE(AVG(amount), 0)  AS avg_amount,
                COALESCE(MAX(amount), 0)  AS max_amount,
                COALESCE(SUM(amount), 0)  AS total_amount
            FROM transactions
            WHERE account_id = $1
              AND created_at >= NOW() - INTERVAL '90 days'
            """,
            account_id,
        )

    return {
        "id": str(account["id"]),
        "customer_name": account["customer_name"],
        "account_type": account["account_type"],
        "status": account["status"],
        "risk_score": float(account["risk_score"]),
        "account_age_days": (
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc) - account["created_at"]
        ).days,
        "last_90_days": {
            "transaction_count": stats["txn_count"],
            "average_amount": round(float(stats["avg_amount"]), 2),
            "max_amount": round(float(stats["max_amount"]), 2),
            "total_volume": round(float(stats["total_amount"]), 2),
        },
    }


async def search_similar_transactions(
    amount_range: str,
    time_window_hours: int = 24,
    category: str | None = None,
) -> dict[str, Any]:
    """Find real transactions matching an amount range within a time window."""
    try:
        low, high = (float(x) for x in amount_range.split("-"))
    except ValueError:
        return {"error": f"Invalid amount_range: {amount_range!r}. Use 'low-high' e.g. '9000-10000'"}

    async with get_connection() as conn:
        query = """
            SELECT t.id, t.account_id, t.amount, t.direction,
                   t.counterparty, t.country_code, t.category, t.created_at,
                   a.customer_name, a.risk_score
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            WHERE t.amount BETWEEN $1 AND $2
              AND t.created_at >= NOW() - ($3 || ' hours')::INTERVAL
        """
        params: list[Any] = [low, high, str(time_window_hours)]

        if category:
            query += " AND t.category = $4"
            params.append(category)

        query += " ORDER BY t.created_at DESC LIMIT 50"
        rows = await conn.fetch(query, *params)

    return {
        "amount_range": amount_range,
        "time_window_hours": time_window_hours,
        "count": len(rows),
        "transactions": [
            {
                "id": str(r["id"]),
                "account_id": str(r["account_id"]),
                "customer_name": r["customer_name"],
                "risk_score": float(r["risk_score"]),
                "amount": float(r["amount"]),
                "direction": r["direction"],
                "counterparty": r["counterparty"],
                "country_code": r["country_code"],
                "category": r["category"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    }
