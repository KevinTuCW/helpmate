# helpmate

An enterprise knowledge-base support copilot. A single-service reference
implementation that combines **RAG** over your documents with **function
calling** for live lookups (orders, logistics): ingest your docs, retrieve
with pgvector, and let a LangGraph flow decide — answer from the knowledge
base, or call a tool.

Part of the "武道AI / AI Engineering Dojo" 阵 (real-combat) series — **阵 01**.

## Stack

FastAPI · LlamaIndex · LangGraph · Postgres + pgvector · pluggable LLM/embeddings.

## How it works

```
question ──> route (LLM tool-choice)
               ├─ order/logistics intent ─> act (query_order / query_logistics)
               └─ otherwise               ─> retrieve (pgvector top-k)
                                                    │
                                              generate (LLM) ──> answer
```

Tools are declared as JSON Schema (OpenAI `tools` format). The `route` node lets
the model decide whether to call a tool and with what arguments; `dispatch_tool`
runs it; the result is fed back to the model to phrase the final answer.

## Quickstart

```bash
docker compose up -d db        # Postgres + pgvector
cp .env.example .env           # set OPENAI_API_KEY (or point to Ollama)
pip install -e ".[dev]"
psql "$DATABASE_URL" -f db/schema.sql
psql "$DATABASE_URL" -f db/seed.sql
uvicorn helpmate.app:app --reload
```

Open http://localhost:8000 — ask a KB question, or `Where is order A1001?`.

## Layout

- `src/helpmate/` — config, ingest, retrieve, tools, providers, graph, app
- `db/` — `schema.sql` (documents / chunks+vector / orders / shipments) + `seed.sql`
- `web/` — static single-page chat
- `tests/` — pytest units (pure logic + fake-LLM router flow)

## Tests

```bash
pip install -e ".[dev]" && pytest -v
```

Pure units (chunking, retrieval formatting, tool dispatch, router flow) run with
no database or API key. DB/LLM paths are exercised via the running service.

## License

MIT
