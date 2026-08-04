# helpmate — PRD

## Problem

Internal support teams answer the same questions over and over, the knowledge
is scattered across wikis/FAQs/PDFs, and order or logistics questions force an
agent to leave the chat and look things up in another system. Response quality
depends on who happens to pick up the ticket.

## Users

Internal customer-support / help-desk agents (primary). Secondarily, end users
if the copilot is later exposed in a self-service widget.

## Core user stories

1. **Ingest knowledge** — I upload a document (FAQ, policy, manual) so the
   copilot can answer from it.
2. **Ask with citations** — I ask a product/policy question and get an answer
   grounded in the knowledge base, with `[n]` citations back to the source.
3. **Live lookups via tools** — I ask "Where is order A1001?" and the copilot
   recognizes it needs data, calls `query_order` / `query_logistics`, and
   answers with the current status — no system-switching.

## Non-goals (v1)

- No ticket workflow / case management.
- No role-based access control or per-document permissions.
- No multi-turn memory beyond a single question.
- No document editing UI (ingestion is API-driven).

## Success metrics

- **Citation rate** — % of KB answers that carry at least one valid `[n]` cite.
- **Tool-call accuracy** — % of order/logistics questions routed to the correct
  tool with the right `order_id`.
- **First-answer hit rate** — % of questions answered without escalation.
- **Latency** — P95 end-to-end response time.

## Out of scope risks tracked

- Hallucinated citations → prompt constrains "answer using ONLY the context".
- Wrong tool / wrong args → measured by tool-call accuracy; router uses the
  model's native tool-choice with strict JSON-Schema parameters.
