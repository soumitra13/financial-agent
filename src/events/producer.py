"""
producer.py — Publish tasks to the Redis Stream.

Stream name : tasks:pending
Dead-letter : tasks:dead

Each message contains the full task payload so the worker is self-contained.
The stream is capped at 10,000 entries (MAXLEN) to avoid unbounded growth.
"""

from __future__ import annotations

from uuid import UUID

import redis

from src.config import get_settings

# ── Stream names ──────────────────────────────────────────────────────────────
STREAM_PENDING   = "tasks:pending"
STREAM_DEAD      = "tasks:dead"
CONSUMER_GROUP   = "agent-workers"
STREAM_MAXLEN    = 10_000


def get_redis() -> redis.Redis:
    """Return a synchronous Redis client (one per process is fine)."""
    settings = get_settings()
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=30,          # higher than BLOCK_MS (5s) to avoid collision
        socket_connect_timeout=5,
    )


def publish_task(
    task_id: UUID | str,
    description: str,
    account_id: str | None = None,
    priority: str = "normal",
) -> str:
    """
    Write a task message to the pending stream.

    Returns the Redis stream message ID (e.g. '1234567890-0').
    """
    r = get_redis()

    # Ensure the consumer group exists (idempotent)
    try:
        r.xgroup_create(STREAM_PENDING, CONSUMER_GROUP, id="0", mkstream=True)
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

    message = {
        "task_id":    str(task_id),
        "description": description,
        "account_id": account_id or "",
        "priority":   priority,
    }

    msg_id = r.xadd(STREAM_PENDING, message, maxlen=STREAM_MAXLEN, approximate=True)
    return msg_id


def move_to_dead_letter(message_id: str, payload: dict, error: str) -> None:
    """Move a failed message to the dead-letter stream for inspection."""
    r = get_redis()
    r.xadd(
        STREAM_DEAD,
        {**payload, "error": error, "original_id": message_id},
        maxlen=1_000,
        approximate=True,
    )
