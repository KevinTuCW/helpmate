-- Chinese full-text search: stop generating content_tsv from raw text.
--
-- `to_tsvector('simple', content)` cannot index Chinese. The default parser
-- classifies characters with the database ctype, so on macOS (en_US.UTF-8) a
-- Chinese run is `blank` and the tsvector comes out empty; on glibc it becomes
-- one giant token. Either way every Chinese query matched 0 rows, which made the
-- FTS half of "hybrid retrieval" dead weight for this corpus.
--
-- content_tsv therefore becomes a plain column, written at ingest from
-- helpmate.retrieve.segment.segment() — jieba words with non-ASCII ones mapped
-- to ASCII surrogates. See that module for why an extension was not used.

ALTER TABLE chunks DROP COLUMN IF EXISTS content_tsv;
ALTER TABLE chunks ADD COLUMN content_tsv tsvector;

DROP INDEX IF EXISTS chunks_tsv_idx;
CREATE INDEX chunks_tsv_idx ON chunks USING gin (content_tsv);
