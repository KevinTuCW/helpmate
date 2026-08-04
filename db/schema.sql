CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS chunks CASCADE;
DROP TABLE IF EXISTS documents CASCADE;

CREATE TABLE documents (
    id          BIGSERIAL PRIMARY KEY,
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
-- HNSW vector index deferred to phase 2 (after embeddings are backfilled).

CREATE TABLE IF NOT EXISTS orders (
    order_id    TEXT PRIMARY KEY,
    customer    TEXT NOT NULL,
    status      TEXT NOT NULL,
    total       NUMERIC(10,2) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS shipments (
    order_id    TEXT PRIMARY KEY REFERENCES orders(order_id) ON DELETE CASCADE,
    carrier     TEXT NOT NULL,
    tracking_no TEXT NOT NULL,
    status      TEXT NOT NULL,
    eta         DATE
);
