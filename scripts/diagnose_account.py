"""
diagnose_account.py — Show transactions for an account and run the pre-analyzer.

Usage:
    python3 scripts/diagnose_account.py [account_id]

    If no account_id is given, uses the highest risk_score account.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv; load_dotenv()

import asyncpg
from src.agent.pre_analyzer import analyze_transactions, build_findings_context


async def main(account_id: str | None = None) -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    conn = await asyncpg.connect(dsn)
    try:
        # Pick account
        if account_id:
            acct = await conn.fetchrow(
                "SELECT id, customer_name, risk_score FROM accounts WHERE id = $1",
                account_id,
            )
        else:
            acct = await conn.fetchrow(
                "SELECT id, customer_name, risk_score FROM accounts ORDER BY risk_score DESC LIMIT 1"
            )

        if not acct:
            print("Account not found.")
            return

        acct_id = str(acct["id"])
        print(f"\nAccount : {acct['customer_name']}  (id={acct_id}, risk={acct['risk_score']:.2f})")
        print("=" * 70)

        # Fetch transactions (same query as the real tool)
        rows = await conn.fetch(
            """
            SELECT id, amount, currency, direction, counterparty,
                   category, country_code, is_flagged, created_at
            FROM transactions
            WHERE account_id = $1
            ORDER BY created_at DESC
            LIMIT 50
            """,
            acct["id"],
        )

        txns = [dict(r) for r in rows]
        for r in txns:
            r["id"] = str(r["id"])
            r["created_at"] = str(r["created_at"])

        print(f"\nTransactions (last {len(txns)}):")
        print(f"  {'ID':8}  {'Amount':>12}  {'Date':16}  {'Category':20}  {'CC':4}  Notes")
        print("  " + "-" * 80)
        amounts = [float(t["amount"]) for t in txns]
        med = sorted(amounts)[len(amounts) // 2] if amounts else 0
        for t in txns:
            cty = t.get("country_code") or "-"
            marker = ""
            amt = float(t["amount"])
            if 8000 <= amt <= 9999:
                marker = " ← structuring?"
            elif cty.upper() in {"NG", "IR", "KP", "SY", "CU", "MM", "BY"}:
                marker = " ← high-risk country"
            elif med > 0 and amt > 3 * med:
                marker = f" ← {amt/med:.1f}x median"
            cat = t.get("category") or "-"
            print(f"  {t['id'][:8]}  ${amt:>11,.2f}  {t['created_at'][:16]}  {cat:<20}  {cty:<4}  {marker}")

        print(f"\n  Median amount: ${med:,.2f}")
        print(f"  Min: ${min(amounts):,.2f}  Max: ${max(amounts):,.2f}")

        # Run pre-analyzer
        print("\n" + "=" * 70)
        print("PRE-ANALYZER OUTPUT:")
        print("=" * 70)
        findings = analyze_transactions(txns)
        ctx = build_findings_context(acct_id, txns, findings)
        print(ctx)

        if not findings:
            print("\n→ No rules triggered. Checking why...")
            structuring = [t for t in txns if 8000 <= float(t["amount"]) <= 9999]
            high_risk = [t for t in txns if (t.get("country_code") or "").upper()
                         in {"NG", "IR", "KP", "SY", "CU", "MM", "BY"}]
            large = [t for t in txns if med > 0 and float(t["amount"]) > 3 * med]
            print(f"  Structuring ($8k-$9.9k) matches : {len(structuring)}")
            print(f"  High-risk country matches        : {len(high_risk)}")
            print(f"  Large amount (>3x median) matches: {len(large)}")
            print("\n  The seed data may not have placed suspicious transactions")
            print("  in this specific account. Try running with a different account.")

            # Find an account that WOULD trigger rules
            print("\n" + "=" * 70)
            print("Searching for accounts with suspicious transactions...")
            structured_rows = await conn.fetch(
                """
                SELECT DISTINCT a.id, a.customer_name, a.risk_score,
                       COUNT(*) FILTER (WHERE t.amount BETWEEN 8000 AND 9999) AS structuring_count,
                       COUNT(*) FILTER (WHERE t.country_code IN ('NG','IR','KP','SY','CU','MM','BY')) AS geo_count
                FROM transactions t
                JOIN accounts a ON a.id = t.account_id
                WHERE t.amount BETWEEN 8000 AND 9999
                   OR t.country_code IN ('NG','IR','KP','SY','CU','MM','BY')
                GROUP BY a.id, a.customer_name, a.risk_score
                ORDER BY a.risk_score DESC
                LIMIT 5
                """
            )
            if structured_rows:
                print("  Accounts with suspicious transactions (structuring or high-risk country):")
                for r in structured_rows:
                    print(f"    {str(r['id'])}  {r['customer_name']:25s}  risk={r['risk_score']:.2f}  "
                          f"structuring={r['structuring_count']}  geo={r['geo_count']}")
                best = structured_rows[0]
                print(f"\nRe-run with: python3 scripts/diagnose_account.py {str(best['id'])}")
            else:
                print("  No suspicious transactions found — seed data may need updating.")
                print("  Check scripts/seed_data.py to ensure high-risk transactions are seeded.")

    finally:
        await conn.close()


if __name__ == "__main__":
    account_id = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(account_id))
