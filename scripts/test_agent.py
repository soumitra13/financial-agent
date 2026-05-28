"""
test_agent.py — End-to-end test of the Financial Agent.

Fetches a high-risk account from the DB, submits a task, and polls until done.

Usage:
    cd ~/Desktop/Financial_Plan_AI
    python3 scripts/test_agent.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

# ── Setup ─────────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

BASE_URL = "http://localhost:8000"


# ── Step 1: Pick a high-risk account ─────────────────────────────────────────
def get_high_risk_account() -> dict:
    """
    Query DB for the account with the most structuring or geographic-risk
    transactions — these are the accounts the pre-analyzer will actually flag.
    Falls back to highest risk_score if none found.
    """
    import asyncio
    import asyncpg

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    async def _fetch():
        conn = await asyncpg.connect(dsn)
        try:
            # Pick account with highest number of suspicious transactions
            row = await conn.fetchrow(
                """
                SELECT a.id, a.customer_name, a.risk_score, a.account_type,
                       COUNT(*) FILTER (WHERE t.amount BETWEEN 8000 AND 9999)   AS structuring,
                       COUNT(*) FILTER (WHERE t.country_code IN
                           ('NG','IR','KP','SY','CU','MM','BY'))                AS geo_risk
                FROM accounts a
                JOIN transactions t ON t.account_id = a.id
                GROUP BY a.id, a.customer_name, a.risk_score, a.account_type
                HAVING
                    COUNT(*) FILTER (WHERE t.amount BETWEEN 8000 AND 9999) > 0
                    OR COUNT(*) FILTER (WHERE t.country_code IN
                        ('NG','IR','KP','SY','CU','MM','BY')) > 0
                ORDER BY (
                    COUNT(*) FILTER (WHERE t.amount BETWEEN 8000 AND 9999) +
                    COUNT(*) FILTER (WHERE t.country_code IN ('NG','IR','KP','SY','CU','MM','BY')) * 2
                ) DESC
                LIMIT 1
                """
            )
            if row:
                return dict(row)
            # Fallback: highest risk score
            row = await conn.fetchrow(
                "SELECT id, customer_name, risk_score, account_type FROM accounts ORDER BY risk_score DESC LIMIT 1"
            )
            return dict(row)
        finally:
            await conn.close()

    return asyncio.run(_fetch())


# ── Step 2: Submit a task ─────────────────────────────────────────────────────
def submit_task(account_id: str, customer_name: str) -> str:
    """POST /tasks and return the task ID."""
    description = (
        f"Analyze the recent transactions for account {account_id} "
        f"belonging to {customer_name}. "
        "Look for any suspicious patterns including structuring, velocity anomalies, "
        "or geographic risk. Flag any anomalies you find and check relevant compliance policies."
    )
    payload = {
        "account_id": account_id,
        "description": description,
    }

    print(f"\nSubmitting task for account: {account_id} ({customer_name})")
    print(f"Query: {description[:80]}...")

    r = httpx.post(f"{BASE_URL}/tasks", json=payload, timeout=15.0)
    if r.status_code not in (200, 201):
        print(f"ERROR: {r.status_code} — {r.text}")
        sys.exit(1)

    data = r.json()
    task_id = data["task_id"]
    print(f"✓ Task created: {task_id}  (status: {data['status']})")
    return task_id


# ── Step 3: Poll until complete ───────────────────────────────────────────────
def poll_task(task_id: str, timeout: int = 300) -> dict:
    """Poll GET /tasks/{id} until status is completed or failed."""
    print(f"\nPolling task {task_id}...")
    deadline = time.time() + timeout
    last_status = None

    while time.time() < deadline:
        r = httpx.get(f"{BASE_URL}/tasks/{task_id}", timeout=10.0)
        if r.status_code != 200:
            print(f"  Poll error: {r.status_code} — {r.text}")
            time.sleep(5)
            continue

        data = r.json()
        status = data.get("status", "unknown")

        if status != last_status:
            print(f"  [{time.strftime('%H:%M:%S')}] Status: {status}")
            last_status = status

        if status in ("completed", "failed"):
            return data

        time.sleep(5)

    print(f"ERROR: Task did not complete within {timeout}s")
    sys.exit(1)


# ── Step 4: Print results ─────────────────────────────────────────────────────
def print_results(task: dict) -> None:
    print("\n" + "=" * 60)
    print("TASK COMPLETE")
    print("=" * 60)
    print(f"Status : {task['status']}")
    print(f"Steps  : {task.get('steps_taken', '?')}")

    result = task.get("result")
    if result:
        print("\n── Agent Result ──────────────────────────────────────────")
        if isinstance(result, dict):
            print(json.dumps(result, indent=2))
        else:
            print(result)
    else:
        print("\n(No result returned)")

    # Fetch audit log
    task_id = task.get("task_id") or task.get("id")
    r = httpx.get(f"{BASE_URL}/tasks/{task_id}/audit", timeout=10.0)
    if r.status_code == 200:
        audit = r.json()
        print(f"\n── Audit Log ({len(audit)} entries) ─────────────────────────")
        for entry in audit:
            step = entry.get("step_number", "?")
            action = entry.get("action", "?")
            detail = entry.get("details", {})
            if isinstance(detail, str):
                try:
                    detail = json.loads(detail)
                except Exception:
                    pass
            tool = detail.get("tool") if isinstance(detail, dict) else ""
            print(f"  Step {step}: {action}" + (f" → {tool}" if tool else ""))


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Financial Agent — End-to-End Test")
    print("=" * 60)

    # Check API is up
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        print(f"API health: {r.json()}")
    except Exception as e:
        print(f"ERROR: Cannot reach API at {BASE_URL}: {e}")
        print("Make sure the server is running: uvicorn src.api.main:app --reload")
        sys.exit(1)

    account = get_high_risk_account()
    # asyncpg returns UUID objects — convert to str for JSON serialisation
    account["id"] = str(account["id"])
    print(f"\nTarget account: {account['customer_name']} "
          f"(risk_score={account['risk_score']}, type={account['account_type']}, "
          f"structuring={account.get('structuring', '?')}, geo_risk={account.get('geo_risk', '?')})")

    task_id = submit_task(account["id"], account["customer_name"])
    task = poll_task(task_id, timeout=1800)  # 30 min — model runs until done
    print_results(task)
