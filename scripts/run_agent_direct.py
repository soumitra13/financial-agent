"""
run_agent_direct.py — Run the agent loop directly, no HTTP, full output.

Shows every step, every error, no timeouts from test scripts.

Usage:
    cd ~/Desktop/Financial_Plan_AI
    python3 scripts/run_agent_direct.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import asyncpg


async def main():
    dsn = os.environ["DATABASE_URL"]

    # 1. Get the highest-risk account
    conn = await asyncpg.connect(dsn)
    row = await conn.fetchrow(
        "SELECT id, customer_name, risk_score FROM accounts ORDER BY risk_score DESC LIMIT 1"
    )
    await conn.close()

    account_id = str(row["id"])
    name = row["customer_name"]
    risk = row["risk_score"]
    print(f"Account: {name}  risk={risk}  id={account_id}\n")

    # 2. Check which model Ollama will use
    from src.config import get_settings
    s = get_settings()
    print(f"LLM provider : {s.llm_provider}")
    print(f"Ollama model : {s.ollama_model}")
    print(f"Ollama URL   : {s.ollama_base_url}\n")

    # 3. Quick Ollama connectivity check
    import httpx
    try:
        r = httpx.get(f"{s.ollama_base_url}/api/tags", timeout=5.0)
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"Ollama models available: {models}")
        if s.ollama_model not in models and not any(s.ollama_model in m for m in models):
            print(f"\n⚠️  WARNING: {s.ollama_model} not found in Ollama!")
            print(f"   Run: ollama pull {s.ollama_model}")
            sys.exit(1)
        print(f"✓ Model {s.ollama_model} is available\n")
    except Exception as e:
        print(f"✗ Cannot reach Ollama: {e}")
        sys.exit(1)

    # 4. Create a task record in the DB
    conn = await asyncpg.connect(dsn)
    task_row = await conn.fetchrow(
        "INSERT INTO tasks (description, status) VALUES ($1, 'pending') RETURNING id",
        f"Analyze transactions for {name} (account {account_id}). "
        "Look for structuring, velocity anomalies, and geographic risk. "
        "Flag suspicious transactions and check compliance policies.",
    )
    await conn.close()
    task_id = task_row["id"]
    print(f"Task ID: {task_id}\n")
    print("=" * 60)
    print("Starting agent loop...")
    print("=" * 60)

    # 5. Run the agent loop directly
    from src.db.connection import init_pool, close_pool
    await init_pool()
    try:
        from src.agent.loop import run_agent
        result = await run_agent(
            task_id=task_id,
            description=(
                f"Analyze transactions for {name} (account {account_id}). "
                "Look for structuring, velocity anomalies, and geographic risk. "
                "Flag suspicious transactions and check compliance policies."
            ),
            account_id=account_id,
        )
        print("\n" + "=" * 60)
        print("RESULT:")
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        import traceback
        print(f"\nERROR: {e}")
        traceback.print_exc()
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
