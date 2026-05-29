"""
worker.py — Runnable entrypoint for the agent worker process.

Usage:
    cd ~/Desktop/Financial_Plan_AI
    python3 -m src.events.worker

Run this in a separate terminal alongside uvicorn.
Handles SIGINT/SIGTERM cleanly.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

# Ensure project root is on the path when run as a module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.observability.logging import configure_logging, get_logger  # noqa: E402

configure_logging()
log = get_logger(__name__)


def _handle_shutdown(signum, frame):
    log.info("worker_shutdown", signal=signum)
    sys.exit(0)


async def main() -> None:
    signal.signal(signal.SIGINT,  _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    log.info("worker_starting", phase="5")

    # Quick Redis connectivity check
    try:
        from src.events.producer import CONSUMER_GROUP, STREAM_PENDING, get_redis
        r = get_redis()
        r.ping()
        log.info("redis_connected", stream=STREAM_PENDING, group=CONSUMER_GROUP)
    except Exception as e:
        log.error("redis_connection_failed", error=str(e),
                  hint="Make sure Redis is running: brew services start redis")
        sys.exit(1)

    from src.events.consumer import run_consumer
    await run_consumer()


if __name__ == "__main__":
    asyncio.run(main())
