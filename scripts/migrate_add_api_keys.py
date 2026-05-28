"""
migrate_add_api_keys.py — Add api_keys table to an existing database.

Run this once against an already-running database (i.e. you don't want
to wipe data with make clean). For fresh installs the table is created
automatically by init.sql on first startup.

Usage (from inside Docker):
    docker compose run --rm seed python3 scripts/migrate_add_api_keys.py

Usage (local):
    DATABASE_URL=postgresql://agent:agent@localhost:5433/financial_agent \
        python3 scripts/migrate_add_api_keys.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import asyncpg

DDL = """
CREATE TABLE IF NOT EXISTS api_keys (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT NOT NULL,
    key_hash     TEXT NOT NULL UNIQUE,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash
    ON api_keys(key_hash);

CREATE INDEX IF NOT EXISTS idx_api_keys_is_active
    ON api_keys(is_active) WHERE is_active = TRUE;

INSERT INTO schema_migrations (version) VALUES ('002_api_keys')
    ON CONFLICT (version) DO NOTHING;
"""


async def run() -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL not set.")
        sys.exit(1)

    print("Connecting to database...", flush=True)
    conn = await asyncpg.connect(dsn)

    try:
        await conn.execute(DDL)
        print("✅ Migration 002_api_keys applied successfully.", flush=True)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
