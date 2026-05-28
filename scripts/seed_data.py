"""
seed_data.py — Generate synthetic accounts and transactions.

Usage:
    cd ~/Desktop/Financial_Plan_AI
    python3 scripts/seed_data.py

Generates:
    - 50 accounts with varying risk profiles
    - ~5000 transactions over 90 days
    - 50-100 planted anomalies:
        * Round-number transfers near $10k (structuring)
        * Rapid successive transactions (velocity)
        * Transfers to high-risk countries
        * Out-of-pattern large amounts (3x account average)
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import asyncpg
from faker import Faker

fake = Faker()
random.seed(42)

# ── Constants ─────────────────────────────────────────────────────────────────

NUM_ACCOUNTS = 50
NUM_TRANSACTIONS = 5000
DAYS_BACK = 90

HIGH_RISK_COUNTRIES = ["NG", "IR", "KP", "MM", "SY", "PK"]
NORMAL_COUNTRIES = ["US", "US", "US", "US", "US", "CA", "GB", "DE", "FR", "AU"]
CATEGORIES = ["wire_transfer", "purchase", "atm", "online", "pos", "transfer"]
COUNTERPARTIES = [
    "Amazon", "Walmart", "Apple", "Chase Bank", "Zelle Transfer",
    "Payroll Direct", "Rent Payment", "Utility Co", "Unknown Entity",
    "Overseas Wire", "Cash Withdrawal",
]


# ── Account generation ────────────────────────────────────────────────────────

def make_accounts(n: int) -> list[dict]:
    accounts = []
    for i in range(n):
        risk = round(random.choices(
            [random.uniform(0.0, 0.3), random.uniform(0.3, 0.6), random.uniform(0.6, 1.0)],
            weights=[0.6, 0.3, 0.1],
        )[0], 2)
        accounts.append({
            "customer_name": fake.name(),
            "account_type": random.choice(["checking", "checking", "savings", "credit"]),
            "status": "active",
            "risk_score": risk,
        })
    return accounts


# ── Transaction generation ────────────────────────────────────────────────────

def make_normal_transaction(account_id: str, avg_amount: float, now: datetime) -> dict:
    days_ago = random.randint(0, DAYS_BACK)
    hours_ago = random.randint(0, 23)
    created_at = now - timedelta(days=days_ago, hours=hours_ago)
    amount = round(max(10.0, random.gauss(avg_amount, avg_amount * 0.4)), 2)
    return {
        "account_id": account_id,
        "amount": amount,
        "currency": "USD",
        "direction": random.choices(["debit", "credit"], weights=[0.65, 0.35])[0],
        "counterparty": random.choice(COUNTERPARTIES),
        "category": random.choice(CATEGORIES),
        "country_code": random.choice(NORMAL_COUNTRIES),
        "is_flagged": False,
        "flag_reason": None,
        "created_at": created_at,
    }


def make_anomalies(account_ids: list[str], now: datetime) -> list[dict]:
    """Plant 50-100 realistic anomalies across random accounts."""
    anomalies = []

    # 1. Structuring — round numbers just below $10k
    for _ in range(20):
        acct = random.choice(account_ids)
        base_time = now - timedelta(days=random.randint(1, 80))
        for offset_hours in [0, 6, 20]:  # 3 transactions within 48 hours
            anomalies.append({
                "account_id": acct,
                "amount": random.choice([9000.0, 9500.0, 9750.0, 9900.0, 9950.0]),
                "currency": "USD",
                "direction": "debit",
                "counterparty": "Unknown Overseas Entity",
                "category": "wire_transfer",
                "country_code": "US",
                "is_flagged": False,
                "flag_reason": None,
                "created_at": base_time + timedelta(hours=offset_hours),
            })

    # 2. Velocity abuse — 6+ transactions in 1 hour
    for _ in range(10):
        acct = random.choice(account_ids)
        base_time = now - timedelta(days=random.randint(1, 60))
        for i in range(random.randint(6, 9)):
            anomalies.append({
                "account_id": acct,
                "amount": round(random.uniform(200, 1500), 2),
                "currency": "USD",
                "direction": "debit",
                "counterparty": fake.company(),
                "category": "online",
                "country_code": "US",
                "is_flagged": False,
                "flag_reason": None,
                "created_at": base_time + timedelta(minutes=i * 7),
            })

    # 3. High-risk country transfers
    for _ in range(20):
        acct = random.choice(account_ids)
        anomalies.append({
            "account_id": acct,
            "amount": round(random.uniform(1000, 15000), 2),
            "currency": "USD",
            "direction": "debit",
            "counterparty": "International Wire Transfer",
            "category": "wire_transfer",
            "country_code": random.choice(HIGH_RISK_COUNTRIES),
            "is_flagged": False,
            "flag_reason": None,
            "created_at": now - timedelta(days=random.randint(1, 85)),
        })

    # 4. Out-of-pattern large amounts (3x normal)
    for _ in range(15):
        acct = random.choice(account_ids)
        anomalies.append({
            "account_id": acct,
            "amount": round(random.uniform(25000, 75000), 2),
            "currency": "USD",
            "direction": "debit",
            "counterparty": "Large Transfer",
            "category": "wire_transfer",
            "country_code": "US",
            "is_flagged": False,
            "flag_reason": None,
            "created_at": now - timedelta(days=random.randint(1, 85)),
        })

    return anomalies


# ── Database insertion ────────────────────────────────────────────────────────

async def seed(dsn: str) -> None:
    print("Connecting to database...")
    conn = await asyncpg.connect(dsn)

    try:
        # Clear existing seed data
        print("Clearing existing data...")
        await conn.execute("DELETE FROM audit_log")
        await conn.execute("DELETE FROM escalations")
        await conn.execute("DELETE FROM tasks")
        await conn.execute("DELETE FROM transactions")
        await conn.execute("DELETE FROM accounts")

        # Insert accounts
        print(f"Inserting {NUM_ACCOUNTS} accounts...")
        accounts_data = make_accounts(NUM_ACCOUNTS)
        account_ids = []
        for a in accounts_data:
            row = await conn.fetchrow(
                """
                INSERT INTO accounts (customer_name, account_type, status, risk_score)
                VALUES ($1, $2, $3, $4) RETURNING id
                """,
                a["customer_name"], a["account_type"], a["status"], a["risk_score"],
            )
            account_ids.append(str(row["id"]))

        print(f"  ✓ {len(account_ids)} accounts created")

        # Generate normal transactions
        now = datetime.now(timezone.utc)
        print(f"Generating {NUM_TRANSACTIONS} normal transactions...")
        normal_txns = []
        per_account = NUM_TRANSACTIONS // NUM_ACCOUNTS
        for acct_id in account_ids:
            avg = round(random.uniform(200, 5000), 2)
            for _ in range(per_account):
                normal_txns.append(make_normal_transaction(acct_id, avg, now))

        # Generate anomalies
        print("Planting anomalies...")
        anomaly_txns = make_anomalies(account_ids, now)
        print(f"  ✓ {len(anomaly_txns)} anomalous transactions planted")

        all_txns = normal_txns + anomaly_txns
        random.shuffle(all_txns)

        # Bulk insert transactions
        print(f"Inserting {len(all_txns)} transactions...")
        await conn.executemany(
            """
            INSERT INTO transactions
                (account_id, amount, currency, direction, counterparty,
                 category, country_code, is_flagged, flag_reason, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            [
                (
                    t["account_id"], t["amount"], t["currency"], t["direction"],
                    t["counterparty"], t["category"], t["country_code"],
                    t["is_flagged"], t["flag_reason"], t["created_at"],
                )
                for t in all_txns
            ],
        )

        # Summary
        total_txns = await conn.fetchval("SELECT COUNT(*) FROM transactions")
        total_accts = await conn.fetchval("SELECT COUNT(*) FROM accounts")
        high_risk = await conn.fetchval(
            "SELECT COUNT(*) FROM transactions WHERE country_code = ANY($1)",
            HIGH_RISK_COUNTRIES,
        )
        print(f"\n✅ Seed complete!")
        print(f"   Accounts:              {total_accts}")
        print(f"   Transactions:          {total_txns}")
        print(f"   High-risk country txns:{high_risk}")
        print(f"   Anomalies planted:     {len(anomaly_txns)}")

    finally:
        await conn.close()


if __name__ == "__main__":
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL not set. Copy .env.example to .env first.")
        sys.exit(1)
    asyncio.run(seed(dsn))
