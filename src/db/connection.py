"""
Async PostgreSQL connection pool using asyncpg.

Usage
-----
Startup (FastAPI lifespan):
    await init_pool()

In a route / service:
    async with get_connection() as conn:
        row = await conn.fetchrow("SELECT ...")

Shutdown:
    await close_pool()
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
from asyncpg import Connection, Pool

logger = logging.getLogger(__name__)

# Module-level pool singleton
_pool: Pool | None = None


async def init_pool(
    dsn: str | None = None,
    min_size: int = 2,
    max_size: int = 10,
) -> Pool:
    """
    Create and store the global asyncpg connection pool.
    Call once at application startup.

    Parameters
    ----------
    dsn:
        PostgreSQL DSN. Falls back to the DATABASE_URL env var if not provided.
    min_size / max_size:
        Pool size bounds. Override via DB_POOL_MIN/MAX_SIZE env vars in settings.
    """
    global _pool

    if _pool is not None:
        return _pool

    if dsn is None:
        import os
        dsn = os.environ["DATABASE_URL"]

    logger.info("Initialising asyncpg pool", extra={"dsn_host": _redact_dsn(dsn)})

    # Neon (and other cloud Postgres providers) require SSL.
    # If the DSN contains sslmode=require we pass ssl="require" to asyncpg,
    # which strips the query-param itself (asyncpg doesn't accept it in the DSN).
    ssl: str | None = None
    if "sslmode=require" in (dsn or ""):
        ssl = "require"
        dsn = dsn.replace("?sslmode=require", "").replace("&sslmode=require", "").replace("sslmode=require", "")

    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=30,
        ssl=ssl,
        # Register pgvector codec so vector columns come back as lists of floats
        init=_register_vector_codec,
    )

    logger.info("asyncpg pool ready", extra={"min": min_size, "max": max_size})
    return _pool


async def close_pool() -> None:
    """Gracefully close the pool. Call at application shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")


def get_pool() -> Pool:
    """
    Return the live pool.
    Raises RuntimeError if init_pool() was never awaited.
    """
    if _pool is None:
        raise RuntimeError("Database pool is not initialised. Call await init_pool() first.")
    return _pool


@asynccontextmanager
async def get_connection() -> AsyncGenerator[Connection, None]:
    """
    Async context manager that acquires a connection from the pool.

    Example
    -------
    async with get_connection() as conn:
        rows = await conn.fetch("SELECT * FROM accounts LIMIT 10")
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def get_transaction() -> AsyncGenerator[Connection, None]:
    """
    Acquire a connection and wrap it in a transaction.
    Automatically commits on success, rolls back on exception.

    Example
    -------
    async with get_transaction() as conn:
        await conn.execute("UPDATE accounts SET status='frozen' WHERE id=$1", acct_id)
        await conn.execute("INSERT INTO audit_log ...")
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn


async def health_check() -> dict:
    """
    Ping the database. Returns a dict with status and server version.
    Used by GET /health.
    """
    try:
        async with get_connection() as conn:
            version = await conn.fetchval("SELECT version()")
            return {"status": "ok", "version": version}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


# ─── Private helpers ──────────────────────────────────────────────────────────

async def _register_vector_codec(conn: Connection) -> None:
    """
    Register a codec so asyncpg can encode/decode pgvector 'vector' columns.
    Without this, reading a vector column raises a codec lookup error.
    """
    await conn.set_type_codec(
        "vector",
        encoder=_encode_vector,
        decoder=_decode_vector,
        schema="public",
        format="text",
    )


def _encode_vector(value: list[float]) -> str:
    """Encode a Python list of floats to pgvector text format: '[0.1,0.2,...]'"""
    return "[" + ",".join(str(v) for v in value) + "]"


def _decode_vector(value: str) -> list[float]:
    """Decode pgvector text format '[0.1,0.2,...]' to a Python list of floats."""
    return [float(v) for v in value.strip("[]").split(",")]


def _redact_dsn(dsn: str) -> str:
    """Remove password from DSN for safe logging."""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(dsn)
        redacted = parsed._replace(netloc=f"{parsed.hostname}:{parsed.port or 5432}")
        return urlunparse(redacted)
    except Exception:
        return "<dsn>"
