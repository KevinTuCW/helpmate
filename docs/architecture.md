# helpmate — Architecture

## Overview

A single FastAPI service. Two entry points: `/ingest` (build the knowledge
base) and `/chat` (answer a question). Answering is orchestrated by a small
LangGraph state machine that first decides whether the question needs a live
tool call or a knowledge-base retrieval, then generates the final answer.

## Components

```
                     ┌──────────────────────────────────────────┐
                     │                FastAPI app                │
                     │                                           │
  POST /ingest ──────┼─> chunk_text ─> embed ─> pgvector (chunks)│
                     │                                           │
  POST /chat  ───────┼─> LangGraph:                              │
                     │      route ──(LLM tool-choice)──┐         │
                     │        │ tool_call?             │ none    │
                     │        ▼                        ▼         │
                     │      act                     retrieve     │
                     │   (query_order /            (pgvector      │
                     │    query_logistics)          top-k)        │
                     │        └────────► generate ◄────┘         │
                     │                  (LLM answer)             │
                     └──────────────────────────────────────────┘
                              │                 │
                        Postgres+pgvector   LLM / Embedder
                     (documents, chunks,     (OpenAI default,
                      orders, shipments)      Ollama-swappable)
```

## Data flow

**Ingest:** text → `chunk_text` (fixed window + overlap) → embed each chunk →
insert into `chunks` with its `document_id` and `embedding`.

**Chat:** `route` calls the LLM with the tool schemas (`tool_choice=auto`).
- If the model returns a tool call → `act` runs `dispatch_tool`, which formats
  the order/shipment row into a context string.
- Otherwise → `retrieve` runs a pgvector cosine search and formats the top-k
  chunks into a numbered, citable context block.
- Both feed `generate`, which builds one prompt from whichever context is
  present and asks the LLM for the final answer.

## Data model

- `documents(id, source, title, created_at)`
- `chunks(id, document_id, chunk_index, content, embedding VECTOR(1536))`
- `orders(order_id, customer, status, total, created_at)`
- `shipments(order_id, carrier, tracking_no, status, eta)`

## Pluggable points

- **Embedder / LLM** — `providers.py` isolates OpenAI behind `embed` /
  `complete` / `select_tool`; swap for Ollama or another vendor.
- **Tools** — `tools.TOOL_SCHEMAS` + `dispatch_tool`; add a tool by declaring a
  schema and a branch. `dispatch_tool` takes its data-access callables as
  arguments, so it is unit-testable without a database.

## Function calling

Tools are declared in the OpenAI `tools` JSON-Schema format. The router relies
on the model's native tool-choice to pick a tool and produce arguments; the
service parses the call, dispatches it, and returns the result to the model.
This mirrors the招/器 series' function-calling material with a runnable path.

## Ingestion note

v1 uses a dependency-light built-in splitter (`chunk_text`) so the core is
fully unit-testable. LlamaIndex (declared in the stack) is the intended upgrade
path for richer loaders/splitters and a `PGVectorStore`-backed index; the
current `db.py` talks to pgvector directly via `psycopg`.

## Deployment

`docker-compose.yml` runs Postgres+pgvector. The app runs under uvicorn. Config
comes from `.env` (`DATABASE_URL`, LLM/embed model + key, `TOP_K`).
