"""
auth/keys.py — API key management.

Key format : fca_<32 hex chars>   e.g. fca_a3f8c2d1...
Storage    : SHA-256 hash of the raw key stored in api_keys table.
             The raw key is returned once at creation and never stored.
Validation : hash the incoming key, look up in DB, check is_active.
"""

from __future__ import annotations

import hashlib
import secrets
from uuid import UUID

from src.db.connection import get_connection

_PREFIX = "fca_"


# ── Key generation ─────────────────────────────────────────────────────────────

def generate_raw_key() -> str:
    """Generate a new raw API key.  Never stored — returned once to caller."""
    return _PREFIX + secrets.token_hex(32)


def hash_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of a raw key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ── Database operations ────────────────────────────────────────────────────────

async def create_key(name: str) -> dict:
    """
    Generate a new key, store its hash, and return the full record
    including the raw key (shown once only).
    """
    raw_key = generate_raw_key()
    key_hash = hash_key(raw_key)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO api_keys (name, key_hash)
            VALUES ($1, $2)
            RETURNING id, name, is_active, created_at
            """,
            name,
            key_hash,
        )

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "key": raw_key,          # ← shown once; caller must save this
        "is_active": row["is_active"],
        "created_at": row["created_at"].isoformat(),
        "note": "Save this key — it will not be shown again.",
    }


async def validate_key(raw_key: str) -> dict | None:
    """
    Validate a raw key against the database.
    Returns the key record (without hash) if valid, None if invalid/inactive.
    Also updates last_used_at.
    """
    if not raw_key or not raw_key.startswith(_PREFIX):
        return None

    key_hash = hash_key(raw_key)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE api_keys
            SET last_used_at = NOW()
            WHERE key_hash = $1 AND is_active = TRUE
            RETURNING id, name, is_active, last_used_at, created_at
            """,
            key_hash,
        )

    if row is None:
        return None

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "is_active": row["is_active"],
        "last_used_at": row["last_used_at"].isoformat() if row["last_used_at"] else None,
        "created_at": row["created_at"].isoformat(),
    }


async def list_keys() -> list[dict]:
    """Return all keys (hashes omitted, raw keys never stored)."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, is_active, last_used_at, created_at
            FROM api_keys
            ORDER BY created_at DESC
            """
        )
    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "is_active": r["is_active"],
            "last_used_at": r["last_used_at"].isoformat() if r["last_used_at"] else None,
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


async def revoke_key(key_id: UUID) -> bool:
    """
    Soft-delete a key by setting is_active = FALSE.
    Returns True if a row was updated, False if key_id not found.
    """
    async with get_connection() as conn:
        result = await conn.execute(
            "UPDATE api_keys SET is_active = FALSE WHERE id = $1 AND is_active = TRUE",
            key_id,
        )
    # result is e.g. "UPDATE 1" or "UPDATE 0"
    return result.endswith("1")


async def key_count() -> int:
    """Return total number of active keys."""
    async with get_connection() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM api_keys WHERE is_active = TRUE"
        )
