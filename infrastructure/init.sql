-- =============================================================================
-- Financial Agent System — Database Schema
-- PostgreSQL 16 + pgvector
-- =============================================================================

-- Enable pgvector for RAG embeddings (all-MiniLM-L6-v2 → 384 dimensions)
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID generation without uuid-ossp (pgcrypto is built-in)
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- =============================================================================
-- ACCOUNTS
-- Holds customer account records with a computed risk score.
-- =============================================================================
CREATE TABLE IF NOT EXISTS accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_name   TEXT NOT NULL,
    account_type    TEXT NOT NULL CHECK (account_type IN ('checking', 'savings', 'credit')),
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'frozen', 'closed')),
    risk_score      NUMERIC(3, 2) NOT NULL DEFAULT 0.0 CHECK (risk_score >= 0.0 AND risk_score <= 1.0),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_accounts_status     ON accounts(status);
CREATE INDEX IF NOT EXISTS idx_accounts_risk_score ON accounts(risk_score DESC);


-- =============================================================================
-- TRANSACTIONS
-- Core financial events. is_flagged / flag_reason are set by the agent.
-- =============================================================================
CREATE TABLE IF NOT EXISTS transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    amount          NUMERIC(12, 2) NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'USD',
    direction       TEXT NOT NULL CHECK (direction IN ('debit', 'credit')),
    counterparty    TEXT,
    category        TEXT,                       -- e.g. wire_transfer, atm, online_purchase
    country_code    TEXT,                       -- ISO 3166-1 alpha-2
    is_flagged      BOOLEAN NOT NULL DEFAULT FALSE,
    flag_reason     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_txn_account_id ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_txn_created_at ON transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_txn_is_flagged  ON transactions(is_flagged) WHERE is_flagged = TRUE;
CREATE INDEX IF NOT EXISTS idx_txn_amount      ON transactions(amount DESC);


-- =============================================================================
-- POLICIES
-- Compliance policy documents chunked and embedded for RAG retrieval.
-- embedding dimension = 384 (all-MiniLM-L6-v2)
-- =============================================================================
CREATE TABLE IF NOT EXISTS policies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,              -- the chunk text
    category        TEXT CHECK (category IN ('aml', 'fraud', 'reporting', 'kyc', 'geographic', 'velocity')),
    embedding       vector(384),                -- filled by seed_policies.py
    effective_date  DATE,
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- IVFFlat index for approximate cosine similarity search
-- lists=10 is appropriate for up to ~10k chunks; bump to 100 for >100k
CREATE INDEX IF NOT EXISTS idx_policy_embedding
    ON policies USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

CREATE INDEX IF NOT EXISTS idx_policy_category ON policies(category);


-- =============================================================================
-- TASKS
-- Each POST /tasks creates a row; the agent loop updates it as it runs.
-- =============================================================================
CREATE TABLE IF NOT EXISTS tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    description     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'escalated')),
    result          JSONB,                      -- final structured output
    agent_model     TEXT,                       -- which LLM was used
    total_steps     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);


-- =============================================================================
-- AUDIT_LOG
-- Immutable record of every agent action. Never delete rows.
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL PRIMARY KEY,
    task_id         UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    step_number     INTEGER NOT NULL,
    action_type     TEXT NOT NULL
                        CHECK (action_type IN ('llm_call', 'tool_call', 'guardrail_check', 'escalation', 'output_validation')),
    action_name     TEXT,                       -- specific tool or check name
    input           JSONB,                      -- what was sent
    output          JSONB,                      -- what came back
    reasoning       TEXT,                       -- agent's chain-of-thought (if captured)
    duration_ms     INTEGER,
    status          TEXT CHECK (status IN ('success', 'failed', 'blocked')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_task_id    ON audit_log(task_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at DESC);


-- =============================================================================
-- ESCALATIONS
-- Created when the agent hits a boundary it can't cross autonomously.
-- =============================================================================
CREATE TABLE IF NOT EXISTS escalations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    reason          TEXT NOT NULL,
    agent_analysis  JSONB,                      -- what the agent found
    severity        TEXT NOT NULL DEFAULT 'medium'
                        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewer_notes  TEXT,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_escalations_status   ON escalations(status);
CREATE INDEX IF NOT EXISTS idx_escalations_severity ON escalations(severity);
CREATE INDEX IF NOT EXISTS idx_escalations_task_id  ON escalations(task_id);


-- =============================================================================
-- HELPER: auto-update updated_at on accounts
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_accounts_updated_at ON accounts;
CREATE TRIGGER set_accounts_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- =============================================================================
-- SCHEMA VERSION (simple tracking)
-- =============================================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_migrations (version) VALUES ('001_initial_schema')
    ON CONFLICT (version) DO NOTHING;


-- =============================================================================
-- API_KEYS
-- Hashed API keys for authenticating requests to the agent API.
-- The raw key is shown once at creation time and never stored.
-- =============================================================================
CREATE TABLE IF NOT EXISTS api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,                  -- human label e.g. "production" or "dev-laptop"
    key_hash    TEXT NOT NULL UNIQUE,           -- SHA-256 hex of the raw key
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash      ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active) WHERE is_active = TRUE;

INSERT INTO schema_migrations (version) VALUES ('002_api_keys')
    ON CONFLICT (version) DO NOTHING;
