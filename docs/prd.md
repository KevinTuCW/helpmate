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
5. **Safe by default** — malicious input (prompt injection, jailbreak, privilege
   probing) is refused before it reaches the model; answers are scrubbed of leaked
   secrets and blocked if they carry disallowed content.
6. **Tenant isolation** — a caller only ever retrieves documents its tenant is
   entitled to; nothing leaks across tenant boundaries.
7. **Follow-up questions** — a short follow-up ("它防水吗？") resolves against the
   session's earlier turns instead of retrieving blind.

## Scope (v1, shipped)

- Real Chinese DJI corpus (manuals / FAQs / policies), structure-aware ingestion
  (HTML + PDF tables) with **boilerplate cleaning**, rich chunk metadata.
- Hybrid retrieval (dense + lexical) + reranking; citations. **(primary path)**
- Function-calling tools for orders/logistics. **(auxiliary — minority of queries)**
- **Governance layer** — input/output guardrails (injection / jailbreak / privilege
  escalation; secret redaction; disallowed-content block), an append-only **audit
  trail** per request, and **multi-tenant permission filtering** on retrieval.
- **Multi-turn memory** — session turns persisted; a history-aware query rewrite
  handles coreference before retrieval (no extra model call).
- Langfuse tracing; reproducible eval harness with a threshold gate wired into
  **CI** (pytest as the hard gate); a fraction of live traffic is **sampled online**
  for later scoring.

## Non-goals (v1)

- No ticket workflow / case management.
- No fine-grained per-document / per-role ACL beyond tenant-level isolation.
- No full online **A/B experimentation** (variant routing + significance) — online
  *sampling* ships; controlled experiments are a later phase.
- No true multimodal ingestion (image OCR / video ASR) — social image/video enters
  as text only; full multimodal is a later phase (阵 04).

## Success metrics

- **Retrieval recall@k** — is the answer-bearing chunk retrieved? *(baseline: recall@5 = 0.91)*
- **Tool-routing accuracy** — order/logistics questions routed to the right tool. *(baseline: 1.0)*
- **Citation rate / precision** — KB answers carry valid `[n]` citations to relevant chunks.
- **Faithfulness / answer relevancy** — via RAGAS (LLM-judge), when enabled.
- **Latency** — P95 end-to-end response time.
- **Guardrail coverage** — every request passes input+output guards; blocked attempts
  and near-misses are recorded in the audit trail.
- **Audit completeness** — one immutable audit row per `/chat` (100% coverage).

## Risks & mitigations

- Hallucinated citations → prompt constrains "answer using ONLY the context";
  citation precision is measured against gold chunks.
- Chinese lexical search → dense (Qwen3, multilingual) handles Chinese semantics;
  Postgres `simple` FTS handles English proper-noun exact matches; RRF fuses both.
- Wrong tool / wrong args → measured by tool-routing accuracy; routing uses the
  model's native tool-choice with strict JSON-Schema parameters.
- Prompt injection / jailbreak → rules-based input guard refuses before any model
  call (no added latency); every attempt is audited.
- Cross-tenant data leakage → retrieval is filtered by `tenant_id` on both legs, so
  a caller can only see its own documents.
- Secret / PII leakage in answers → output guard redacts secrets and the audit trail
  stores an answer *hash*, not the answer text.
