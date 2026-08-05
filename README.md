# helpmate

A production-grade **enterprise knowledge-base support copilot**. helpmate answers
customer-support questions grounded in a real Chinese-language knowledge base
(built from public DJI documentation) and calls live tools for order/logistics
lookups — with hybrid retrieval, reranking, full-chain tracing, and a
reproducible evaluation harness.

Part of the "武道AI / AI Engineering Dojo" 阵 (real-combat) series — **阵 01**.

## What it does

- **RAG over a real Chinese corpus** — 17 DJI documents (manuals, FAQs, policies) →
  926 chunks. Chinese-dominant text with English proper nouns (OcuSync, RTH, DJI Care…).
- **Hybrid retrieval** — dense (Qwen3-Embedding) + sparse (Postgres full-text) fused
  with Reciprocal Rank Fusion, then reranked by Qwen3-Reranker.
- **Function calling** — order/logistics questions route to `query_order` /
  `query_logistics` tools instead of the knowledge base.
- **Grounded answers with citations** — every KB answer cites its sources `[n]`.
- **Observability** — every request is traced in Langfuse (generations, retrieval,
  tools, tokens, latency).
- **Evaluation** — a 50-item human-verified golden set + metrics (recall@k, MRR,
  nDCG, tool-routing, citation) with a threshold gate.

## How it works

```
question ─▶ route (GLM tool-choice)
              ├─ order/logistics ─▶ act: query_order / query_logistics ─┐
              └─ knowledge        ─▶ retrieve (hybrid) ─▶ rerank ────────┤
                                                                        ▼
                                                            generate (GLM) ─▶ answer[n]
```

## Stack

| Concern | Choice |
| --- | --- |
| API / orchestration | FastAPI · LangGraph |
| LLM | **GLM-4.7** via z.ai (OpenAI-compatible) |
| Embeddings | **Qwen3-Embedding-8B** (dim 1024) via SiliconFlow |
| Reranker | **Qwen3-Reranker-8B** via SiliconFlow |
| Vector + lexical store | Postgres 16 + **pgvector** (HNSW) + `tsvector` (GIN) |
| Ingestion | BeautifulSoup (HTML) · PyMuPDF (PDF + tables) · structure-aware chunking |
| Observability | **Langfuse** (v4) |
| Evaluation | custom metrics + **RAGAS** (optional) |

Providers are OpenAI-compatible and swappable via `.env`.

## Quickstart

```bash
# 1. Postgres + pgvector (local Homebrew or docker)
psql "$DATABASE_URL" -v dim=1024 -f db/schema.sql
psql "$DATABASE_URL" -f db/seed.sql

# 2. Config: GLM (z.ai), SiliconFlow (Qwen3), Langfuse keys
cp .env.example .env   # then fill in keys

# 3. Install + build the knowledge base
pip install -e ".[dev]"
python scripts/fetch_corpus.py      # fetch DJI corpus (corpus/sources.tsv)
python scripts/ingest_corpus.py     # ingest → chunks
python scripts/backfill_embeddings.py   # Qwen3 embeddings + HNSW

# 4. Run
uvicorn helpmate.app:app --reload
```

Ask a KB question, or `Where is order A1001?`.

## Evaluation

```bash
python eval/run_eval.py            # retrieval + tool metrics -> eval/report.md
# generation-quality metrics (citation + RAGAS) are gated behind eval_generate=True
```

Latest baseline: **recall@5 = 0.91 · tool-routing = 1.0 · gate PASS**.

## Layout

- `src/helpmate/` — `config`, `obs` (Langfuse), `ingest/` (loaders, chunking, pipeline),
  `retrieve/` (embed, fuse, rerank, hybrid, context), `providers`, `tools`, `graph`, `app`
- `db/` — `schema.sql` (documents / chunks + vector + tsvector / orders / shipments), `seed.sql`
- `corpus/` — source list + manifest (raw bytes gitignored)
- `eval/` — golden set, metrics, runner, report
- `tests/` — pytest units
- `docs/` — PRD + architecture

## License

MIT
