"""
check_task.py — Full diagnostic: DB tasks + audit log + Redis stream state.

Usage:
    python3 scripts/check_task.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv

load_dotenv()
import asyncpg
import redis as redis_lib


async def check_db():
    dsn = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(dsn)

    rows = await conn.fetch("""
        SELECT id, status, total_steps, result, created_at, completed_at
        FROM tasks ORDER BY created_at DESC LIMIT 5
    """)

    print("=== Latest Tasks (DB) ===")
    for r in rows:
        result = r["result"]
        if isinstance(result, str):
            try: result = json.loads(result)
            except: pass
        error = (result or {}).get("error") if isinstance(result, dict) else None
        print(f"\n  ID      : {r['id']}")
        print(f"  Status  : {r['status']}")
        print(f"  Steps   : {r['total_steps']}")
        print(f"  Created : {r['created_at']}")
        print(f"  Done    : {r['completed_at']}")
        if error:
            print(f"  ERROR   : {error}")
        elif result:
            print(f"  Summary : {str((result or {}).get('summary',''))[:120]}")

    if rows:
        task_id = rows[0]["id"]
        audits = await conn.fetch("""
            SELECT step_number, action_type, action_name, status, duration_ms, output
            FROM audit_log WHERE task_id = $1 ORDER BY step_number, id
        """, task_id)
        print(f"\n=== Audit Log for latest task ({len(audits)} entries) ===")
        if not audits:
            print("  (none — worker never reached run_agent)")
        for a in audits:
            out = a["output"]
            if isinstance(out, str):
                try: out = json.loads(out)
                except: pass
            err = (out or {}).get("error") if isinstance(out, dict) else None
            line = f"  Step {a['step_number']} | {a['action_type']:12} | {a['action_name'] or '':30} | {a['status']} | {a['duration_ms']}ms"
            if err:
                line += f"\n    ↳ ERROR: {err}"
            print(line)

    await conn.close()


def check_redis():
    print("\n=== Redis Stream State ===")
    try:
        r = redis_lib.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"),
                               decode_responses=True)
        r.ping()

        # Pending stream length
        length = r.xlen("tasks:pending")
        print(f"  tasks:pending length : {length}")

        # Consumer group info
        try:
            groups = r.xinfo_groups("tasks:pending")
            for g in groups:
                print(f"  Group '{g['name']}' : pending={g['pending']} consumers={g['consumers']}")
        except Exception:
            print("  (no consumer group yet)")

        # Dead-letter stream
        dead_len = r.xlen("tasks:dead") if r.exists("tasks:dead") else 0
        print(f"  tasks:dead length    : {dead_len}")

        if dead_len > 0:
            print("\n=== Dead-Letter Entries ===")
            entries = r.xrange("tasks:dead", count=5)
            for msg_id, payload in entries:
                print(f"\n  msg_id : {msg_id}")
                print(f"  task   : {payload.get('task_id', '?')}")
                print(f"  error  : {payload.get('error', '?')}")

    except Exception as e:
        print(f"  Redis error: {e}")


if __name__ == "__main__":
    asyncio.run(check_db())
    check_redis()
