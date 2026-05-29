"""
consumer.py — Read tasks from the Redis Stream and run the agent.

Flow:
  1. XREADGROUP blocks for up to 5s waiting for new messages
  2. For each message → run_agent(task_id, description, account_id)
  3. On success → XACK (removes from PEL)
  4. On failure → move to dead-letter stream, XACK to clear PEL
  5. On startup → reclaim any messages pending > 60s (crashed workers)

Consumer group : agent-workers
Consumer name  : set per process (worker-{pid})
"""

from __future__ import annotations

import asyncio
import os
import time
from uuid import UUID

import redis

from src.events.producer import (
    CONSUMER_GROUP,
    STREAM_DEAD,
    STREAM_PENDING,
    get_redis,
    move_to_dead_letter,
)

BLOCK_MS         = 5_000   # how long XREADGROUP blocks waiting for messages
CLAIM_IDLE_MS    = 60_000  # reclaim messages idle this long (crashed worker)
MAX_RETRIES      = 3       # dead-letter after this many failed attempts
HEARTBEAT_SEC    = 30      # worker prints a heartbeat line every N seconds


def _consumer_name() -> str:
    return f"worker-{os.getpid()}"


async def process_message(message_id: str, payload: dict) -> None:
    """Run the agent for one stream message."""
    from src.agent.loop import run_agent

    task_id_str = payload.get("task_id", "")
    description = payload.get("description", "")
    account_id  = payload.get("account_id") or None

    print(f"  [consumer] Processing task {task_id_str}", flush=True)

    task_id = UUID(task_id_str)
    await run_agent(task_id=task_id, description=description, account_id=account_id)


async def reclaim_stalled(r: redis.Redis) -> None:
    """
    On startup, adopt any messages that a previous worker started but never acked.
    These are messages in the PEL (pending entries list) idle > CLAIM_IDLE_MS.
    """
    consumer = _consumer_name()
    try:
        # XAUTOCLAIM: atomically transfer idle PEL entries to this consumer
        result = r.xautoclaim(
            STREAM_PENDING,
            CONSUMER_GROUP,
            consumer,
            min_idle_time=CLAIM_IDLE_MS,
            start_id="0-0",
            count=10,
        )
        claimed = result[1] if isinstance(result, (list, tuple)) else []
        if claimed:
            print(f"[consumer] Reclaimed {len(claimed)} stalled message(s)", flush=True)
    except redis.exceptions.ResponseError:
        # Redis < 7 doesn't have XAUTOCLAIM — skip silently
        pass


async def run_consumer() -> None:
    """
    Main consumer loop. Runs until the process is killed.
    Uses asyncio for the agent loop, sync redis for stream ops.
    """
    from src.db.connection import init_pool
    await init_pool()

    r = get_redis()
    consumer = _consumer_name()
    last_heartbeat = time.monotonic()

    print(f"[consumer] Started — group={CONSUMER_GROUP} consumer={consumer}", flush=True)
    print(f"[consumer] Listening on stream: {STREAM_PENDING}", flush=True)

    # Ensure stream + consumer group exist before reading
    try:
        r.xgroup_create(STREAM_PENDING, CONSUMER_GROUP, id="0", mkstream=True)
        print(f"[consumer] Created consumer group '{CONSUMER_GROUP}'", flush=True)
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print("[consumer] Consumer group already exists — OK", flush=True)
        else:
            raise

    await reclaim_stalled(r)

    while True:
        # Heartbeat
        now = time.monotonic()
        if now - last_heartbeat >= HEARTBEAT_SEC:
            pending = r.xpending(STREAM_PENDING, CONSUMER_GROUP)
            count = pending.get("pending", 0) if isinstance(pending, dict) else 0
            print(f"[consumer] ♥ alive — pending={count}", flush=True)
            last_heartbeat = now

        # Read new messages
        try:
            results = r.xreadgroup(
                CONSUMER_GROUP,
                consumer,
                {STREAM_PENDING: ">"},
                count=1,
                block=BLOCK_MS,
            )
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            print(f"[consumer] Redis transient error: {e} — retrying in 2s", flush=True)
            await asyncio.sleep(2)
            continue

        if not results:
            continue  # timeout, loop again

        for stream_name, messages in results:
            for message_id, payload in messages:
                task_id = payload.get("task_id", "?")
                print(f"\n[consumer] ← message {message_id}  task={task_id}", flush=True)

                try:
                    await process_message(message_id, payload)
                    # Success — acknowledge
                    r.xack(STREAM_PENDING, CONSUMER_GROUP, message_id)
                    print(f"[consumer] ✓ acked {message_id}", flush=True)

                except Exception as exc:
                    import traceback
                    tb = traceback.format_exc()
                    print(f"[consumer] ✗ FAILED {message_id}: {exc}\n{tb}", flush=True)
                    move_to_dead_letter(message_id, payload, repr(exc))
                    r.xack(STREAM_PENDING, CONSUMER_GROUP, message_id)
                    print(f"[consumer] → moved to dead-letter: {STREAM_DEAD}", flush=True)
