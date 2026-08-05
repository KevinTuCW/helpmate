# helpmate — PRD

## Problem

Enterprise support teams answer the same questions repeatedly, knowledge is
scattered across manuals / FAQs / policy pages / PDFs, and order or logistics
questions force an agent to leave the conversation and look things up in another
system. Answer quality depends on whoever picks up the ticket. Source material is
**Chinese-dominant with many English proper nouns** (product names, feature
acronyms like OcuSync/RTH, program names like DJI Care), which trips up naive
retrieval.

## Users

Internal customer-support / help-desk agents (primary). Secondarily, end users if
the copilot is exposed in a self-service widget.

## Core user stories

1. **Answer from the knowledge base with citations** — an agent asks a product,
   policy, or troubleshooting question and gets an answer grounded in the real
   documentation, with `[n]` citations back to the source chunk.
2. **Handle Chinese + English-proper-noun queries** — retrieval works for
   Chinese semantic questions *and* exact English proper-noun matches (e.g.
   "DJI Care 随心换", "Ocusync").
3. **Live lookups via tools** — "Where is order A1001?" routes to
   `query_order` / `query_logistics` and answers with current status — no
   system-switching.
4. **Trust & debuggability** — every request is traceable end-to-end
   (retrieval, tools, LLM, tokens, latency) so quality can be inspected.

## Scope (v2, shipped)

- Real Chinese DJI corpus (manuals / FAQs / policies), structure-aware ingestion
  (HTML + PDF tables), rich chunk metadata.
- Hybrid retrieval (dense + lexical) + reranking; citations. **(primary path)**
- Function-calling tools for orders/logistics. **(auxiliary — minority of queries)**
- Langfuse tracing; reproducible eval harness with a threshold gate.

## Non-goals (v2)

- No ticket workflow / case management.
- No role-based access control or per-document permissions.
- No multi-turn memory beyond a single question (session_id is captured for later).
- No true multimodal ingestion (image OCR / video ASR) — social image/video enters
  as text only; full multimodal is a later phase.

## Success metrics

- **Retrieval recall@k** — is the answer-bearing chunk retrieved? *(baseline: recall@5 = 0.91)*
- **Tool-routing accuracy** — order/logistics questions routed to the right tool. *(baseline: 1.0)*
- **Citation rate / precision** — KB answers carry valid `[n]` citations to relevant chunks.
- **Faithfulness / answer relevancy** — via RAGAS (LLM-judge), when enabled.
- **Latency** — P95 end-to-end response time.

## Risks & mitigations

- Hallucinated citations → prompt constrains "answer using ONLY the context";
  citation precision is measured against gold chunks.
- Chinese lexical search → dense (Qwen3, multilingual) handles Chinese semantics;
  Postgres `simple` FTS handles English proper-noun exact matches; RRF fuses both.
- Wrong tool / wrong args → measured by tool-routing accuracy; routing uses the
  model's native tool-choice with strict JSON-Schema parameters.
