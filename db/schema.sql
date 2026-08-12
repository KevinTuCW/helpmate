CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS chunks CASCADE;
DROP TABLE IF EXISTS documents CASCADE;

CREATE TABLE documents (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL DEFAULT 'public',   -- multi-tenant permission boundary
    source_url  TEXT NOT NULL,
    title       TEXT,
    doc_type    TEXT NOT NULL,              -- faq|policy|spec|manual|social
    product     TEXT,
    lang        TEXT DEFAULT 'zh',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id            BIGSERIAL PRIMARY KEY,
    document_id   BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tenant_id     TEXT NOT NULL DEFAULT 'public',  -- denormalized for retrieval filtering
    chunk_index   INT NOT NULL,
    content       TEXT NOT NULL,
    section_title TEXT,
    doc_type      TEXT NOT NULL,
    product       TEXT,
    source_url    TEXT,
    lang          TEXT DEFAULT 'zh',
    embedding     VECTOR(1024),             -- filled in phase 2
    content_tsv   tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX chunks_tsv_idx ON chunks USING gin (content_tsv);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tenant_idx ON chunks (tenant_id);

-- Append-only audit trail: one row per /chat, for governance & traceability.
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL DEFAULT 'public',
    session_id  TEXT,
    question    TEXT NOT NULL,
    decision    TEXT NOT NULL,              -- retrieve|act|blocked_input|blocked_output
    tool_call   TEXT,
    guard       TEXT,                       -- comma-joined guardrail reasons, if any
    answer_hash TEXT,                       -- sha256 of the answer (content-free trace)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_session_idx ON audit_log (session_id, created_at);

-- Multi-turn conversation memory: ordered turns per session.
CREATE TABLE IF NOT EXISTS session_turns (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,              -- user|assistant
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS session_turns_idx ON session_turns (session_id, id);

-- Online sampling: a fraction of live traffic captured for later offline scoring.
CREATE TABLE IF NOT EXISTS online_eval (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL DEFAULT 'public',
    session_id  TEXT,
    question    TEXT NOT NULL,
    answer      TEXT,
    hit_ids     TEXT,                       -- comma-joined retrieved chunk ids
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Orders carry the same ownership columns as the corpus: retrieval filters by
-- tenant, order lookups additionally filter by customer, so the Function-Calling
-- side cannot become a horizontal-privilege hole.
CREATE TABLE IF NOT EXISTS orders (
    order_id    TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL DEFAULT 'public',   -- tenant boundary
    customer_id TEXT NOT NULL,                    -- ownership boundary
    customer    TEXT NOT NULL,
    status      TEXT NOT NULL,
    total       NUMERIC(10,2) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS orders_owner_idx ON orders (tenant_id, customer_id);
CREATE TABLE IF NOT EXISTS shipments (
    order_id    TEXT PRIMARY KEY REFERENCES orders(order_id) ON DELETE CASCADE,
    carrier     TEXT NOT NULL,
    tracking_no TEXT NOT NULL,
    status      TEXT NOT NULL,
    eta         DATE
);
