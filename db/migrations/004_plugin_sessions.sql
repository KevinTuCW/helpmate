-- 004 — conversation plugin session bridge.
--
-- Apply with:
--   psql "$DATABASE_URL" -f db/migrations/004_plugin_sessions.sql

CREATE TABLE IF NOT EXISTS plugin_sessions (
  id             bigserial   PRIMARY KEY,
  tenant_id      text        NOT NULL,
  session_id     text        NOT NULL,
  plugin         text        NOT NULL,
  ext_session_id text        NOT NULL,
  active         boolean     NOT NULL DEFAULT true,
  opened_at      timestamptz NOT NULL DEFAULT now(),
  closed_at      timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS plugin_sessions_one_active
  ON plugin_sessions (tenant_id, session_id, plugin) WHERE active;

CREATE INDEX IF NOT EXISTS plugin_sessions_lookup
  ON plugin_sessions (tenant_id, session_id) WHERE active;
