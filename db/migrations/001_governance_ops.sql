-- Migration 001: governance + ops (安全与治理 / 运营成熟度).
-- Non-destructive — apply this on an existing populated DB instead of re-running
-- schema.sql (which DROPs chunks/documents and would force a full re-ingest).
--   psql "$DATABASE_URL" -f db/migrations/001_governance_ops.sql

-- multi-tenant permission boundary
ALTER TABLE documents ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'public';
ALTER TABLE chunks    ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'public';
CREATE INDEX IF NOT EXISTS chunks_tenant_idx ON chunks (tenant_id);

-- append-only audit trail
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL DEFAULT 'public',
    session_id  TEXT,
    question    TEXT NOT NULL,
    decision    TEXT NOT NULL,
    tool_call   TEXT,
    guard       TEXT,
    answer_hash TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_session_idx ON audit_log (session_id, created_at);

-- multi-turn conversation memory
CREATE TABLE IF NOT EXISTS session_turns (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS session_turns_idx ON session_turns (session_id, id);

-- online sampling capture
CREATE TABLE IF NOT EXISTS online_eval (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL DEFAULT 'public',
    session_id  TEXT,
    question    TEXT NOT NULL,
    answer      TEXT,
    hit_ids     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
