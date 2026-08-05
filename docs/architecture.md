# helpmate — Architecture

A single FastAPI service with two entry points: `/ingest` (build the knowledge
base) and `/chat` (answer a question). The **primary path is knowledge-base
question answering** (hybrid retrieval → rerank → cited generation); a LangGraph
state machine **defaults to retrieval** and only branches to an **auxiliary**
tool call for the minority of order/logistics queries. Every request is traced
in Langfuse.

## System overview

```
                              ┌───────────────────────── FastAPI (app.py) ─────────────────────────┐
  POST /ingest ──────────────▶│ loaders → chunking → pipeline → (Qwen3 embed) → Postgres           │
                              │                                                                     │
  POST /chat  ──▶ @observe ──▶│ LangGraph (graph.py):                                               │
   (Langfuse root trace)      │    route ──(GLM tool-choice)──┐                                     │
                              │      │ tool_call?             │ none                                │
                              │      ▼                        ▼                                     │
                              │    act (dispatch_tool)     retrieve (hybrid) ──▶ rerank (Qwen3)     │
                              │      │  query_order /          │  dense (pgvector)                   │
                              │      │  query_logistics        │  + sparse (tsvector) ── RRF         │
                              │      └────────► generate (GLM) ◄┘                                    │
                              │                    │ answer with [n] citations                      │
                              └────────────────────┼────────────────────────────────────────────────┘
                                   Postgres 16 + pgvector          z.ai (GLM-4.7)   SiliconFlow (Qwen3)
                               documents / chunks(vector,tsv)                        embed + rerank
                               orders / shipments                        Langfuse (all spans)
```

## Ingestion pipeline (`ingest/`)

- **loaders.py** — `clean_html` (BeautifulSoup; drops nav/footer/scripts, and
  **preserves `<h1>–<h6>` as `#`-prefixed headings** so sections survive),
  `table_to_markdown`, `load_pdf` (PyMuPDF: text + tables → Markdown).
- **chunking.py** — `chunk_text` (windowed w/ overlap), `split_sections` (by
  headings), `chunk_document` (text windowed, tables kept whole, each chunk tagged
  with `section_title` + `doc_type` + `product` + `source_url` + `lang`).
- **pipeline.py** — `ingest_source(kind, ...)` orchestrates load → chunk → write.
- **Corpus** — `scripts/fetch_corpus.py` pulls a manifest of real DJI Chinese
  pages/PDFs into `corpus/`; `scripts/ingest_corpus.py` batch-ingests them;
  `scripts/backfill_embeddings.py` fills embeddings + builds the HNSW index.

## Retrieval (`retrieve/`)

Hybrid, so Chinese semantics and English proper nouns are both covered:

- **embed.py** — `Qwen3Embedder` (SiliconFlow `Qwen/Qwen3-Embedding-8B`,
  `dimensions=1024` to match the schema); `get_embedder()` (local hashing fallback
  for offline tests).
- **db.dense_search** — pgvector cosine over the HNSW index.
- **db.fts_search** — Postgres `websearch_to_tsquery('simple', …)` over a GIN
  `tsvector` — English proper nouns index cleanly; Chinese is left to dense.
- **fuse.py** — `rrf_fuse` (Reciprocal Rank Fusion) merges the two rankings.
- **rerank.py** — `Qwen/Qwen3-Reranker-8B` reorders the fused candidates to top-k.
- **hybrid.py** — `hybrid_retrieve(query)` chains embed → dense+fts → RRF → rerank.
- **context.py** — `format_context` renders top-k chunks as a numbered, citable block.

## Generation & orchestration (`graph.py`, `providers.py`)

- LangGraph nodes: `route` → (`act` | `retrieve` → rerank) → `generate`.
- `route`/`generate` call **GLM-4.7** (`OpenAILLM`, z.ai base URL, thinking-on).
- Prompt constrains answers to the provided context and preserves `[n]` citations;
  refuses when context is insufficient.

## Function calling (`tools.py`) — auxiliary

An **auxiliary** capability, not the main path: it only serves the minority of
real-time order/logistics queries; everything else goes through knowledge-base
retrieval. Tools are declared in OpenAI `tools` JSON-Schema format (`query_order`,
`query_logistics`). `route` uses the model's native tool-choice (defaulting to
retrieval); `dispatch_tool` runs the selected tool against `orders`/`shipments`.
Tool results feed `generate`.

## Data model

- `documents(id, source_url, title, doc_type, product, lang, created_at)`
- `chunks(id, document_id, chunk_index, content, section_title, doc_type, product,
  source_url, lang, embedding VECTOR(1024), content_tsv tsvector)` —
  HNSW index on `embedding`, GIN index on `content_tsv`.
- `orders(order_id, customer, status, total, created_at)`
- `shipments(order_id, carrier, tracking_no, status, eta)`

## Observability (`obs.py`)

Langfuse v4. The `langfuse.openai` drop-in auto-captures GLM/Qwen3 calls as
`generation`/`embedding` observations (model + tokens). `@observe` types the tree:
`retrieve-context` (retriever), `rerank-candidates` (span), `tool:<name>` (tool),
under a `chat-response` root trace with question/answer I/O, `session_id`, `tags`,
`environment`, and a recursive PII/secret mask.

## Evaluation (`eval/`)

- `golden.jsonl` — 50 human-verified items (policy/faq/manual/order); each carries
  `gold_chunk_ids` (the answer-bearing chunk) and, for tool questions, `expected_tool`.
- `metrics.py` — recall@k, MRR, nDCG, tool-routing, citation precision (pure, tested).
- `run_eval.py` — runs the golden set, writes `report.md`/`report.json` with a
  threshold gate. Generation-dependent metrics (citation + RAGAS) are gated behind
  `eval_generate` (off by default; glm-4.7 generation is slow).
- `ragas_eval.py` — RAGAS faithfulness / answer-relevancy / context precision & recall
  (judge = GLM, embeddings = Qwen3).

## Configuration (`config.py`)

All providers are OpenAI-compatible and env-driven: `LLM_*` (GLM on z.ai),
`SILICONFLOW_*` + `EMBED_*`/`RERANK_MODEL` (Qwen3), `LANGFUSE_*`, `DATABASE_URL`,
retrieval (`TOP_K`, `retrieve_candidates`) and eval knobs (`eval_recall_k`,
`eval_generate`, `eval_thresholds`).

## Deployment

Postgres 16 + pgvector (local Homebrew or docker-compose). App runs under uvicorn.
Python 3.12.
