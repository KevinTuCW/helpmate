import helpmate.obs  # noqa: F401  -- initializes Langfuse before any OpenAI client
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from langfuse import observe, get_client, propagate_attributes

from helpmate import db
from helpmate.auth import Principal, require_principal
from helpmate.config import get_settings
from helpmate.tools import dispatch_tool
from helpmate.providers import OpenAILLM
from helpmate.retrieve.embed import get_embedder
from helpmate.retrieve.hybrid import hybrid_retrieve
from helpmate.ingest.pipeline import ingest_source
from helpmate.graph import build_graph
from helpmate.security import (check_input, check_output, redact_pii,
                               REFUSAL_INPUT, REFUSAL_OUTPUT)
from helpmate.session import rewrite_query
from helpmate.ops import should_sample

app = FastAPI(title="helpmate")
WEB = Path(__file__).resolve().parents[2] / "web"


class IngestReq(BaseModel):
    source: str
    title: str
    text: str


class ChatReq(BaseModel):
    question: str
    session_id: str | None = None
    # No tenant_id here on purpose: identity comes from the credential, never
    # from the request body. A caller must not be able to name its own tenant.


@app.post("/ingest")
def ingest(req: IngestReq, principal: Principal = Depends(require_principal)):
    """Ingest one document for the caller's tenant and embed *its* chunks only."""
    s = get_settings()
    r = ingest_source(kind="html", path_or_html=req.text,
                      meta={"source_url": req.source, "title": req.title,
                            "doc_type": "faq", "product": None, "lang": "zh",
                            "tenant_id": principal.tenant_id})
    embedder = get_embedder()
    embedded = 0
    while embedded < s.ingest_max_chunks:
        rows = db.fetch_unembedded(32, document_id=r["document_id"])
        if not rows:
            break
        vecs = embedder.embed_batch([c for _, c in rows])
        for (cid, _), v in zip(rows, vecs):
            db.update_embedding(cid, v)
        embedded += len(rows)
    return {**r, "embedded": embedded}


@app.post("/chat")
@observe(name="chat-response", capture_input=False)
def chat(req: ChatReq, principal: Principal = Depends(require_principal)):
    s = get_settings()
    tenant = principal.tenant_id
    attrs = {"tags": ["chat"]}
    if req.session_id:
        attrs["session_id"] = req.session_id
    with propagate_attributes(**attrs):
        get_client().set_current_trace_io(input=req.question)

        # input guardrail — refuse injection/jailbreak/escalation before any model call
        if s.guardrails_enabled:
            gin = check_input(req.question)
            if gin.blocked:
                db.write_audit(tenant_id=tenant, session_id=req.session_id,
                               question=redact_pii(req.question), decision="blocked_input",
                               tool_call=None, guard=gin.reasons, answer="")
                get_client().set_current_trace_io(input=req.question, output=REFUSAL_INPUT)
                return {"answer": REFUSAL_INPUT, "hits": [], "tool_call": None,
                        "blocked": True, "guard": gin.reasons}

        # multi-turn: enrich the retrieval query with recent history (coreference)
        history = (db.recent_turns(req.session_id, s.session_history_turns)
                   if req.session_id else [])
        retrieval_query = rewrite_query(req.question, history)

        run = build_graph(
            retriever=lambda q: hybrid_retrieve(q, tenant_id=tenant),
            # Order lookups are bound to the authenticated principal, so a
            # stranger's order_id resolves to "not found" instead of leaking.
            tool_dispatch=lambda name, args: dispatch_tool(
                name, args,
                get_order=lambda oid: db.get_order(
                    oid, tenant_id=principal.tenant_id,
                    customer_id=principal.customer_id),
                get_shipment=lambda oid: db.get_shipment(
                    oid, tenant_id=principal.tenant_id,
                    customer_id=principal.customer_id),
            ),
            llm=OpenAILLM(),
        )
        state = run(req.question, retrieval_query=retrieval_query)
        answer = state["answer"]

        # output guardrail — redact leaked secrets, hard-block disallowed content
        guard_reasons: list[str] = []
        decision = "act" if state.get("tool_call") else "retrieve"
        if s.guardrails_enabled:
            gout = check_output(answer)
            guard_reasons = gout.reasons
            if gout.blocked:
                answer, decision = REFUSAL_OUTPUT, "blocked_output"
            else:
                answer = gout.text

        # governance: audit every turn; multi-turn: persist the exchange
        tool_name = (state.get("tool_call") or {}).get("name")
        db.write_audit(tenant_id=tenant, session_id=req.session_id,
                       question=redact_pii(req.question),
                       decision=decision, tool_call=tool_name, guard=guard_reasons,
                       answer=answer)
        if req.session_id:
            db.append_turn(req.session_id, "user", req.question)
            db.append_turn(req.session_id, "assistant", answer)

        # ops: sample a fraction of live traffic for offline scoring
        hit_ids = [h.get("chunk_id") for h in state.get("hits", [])]
        if should_sample(req.session_id or req.question, s.online_sample_rate):
            db.capture_sample(tenant_id=tenant, session_id=req.session_id,
                              question=redact_pii(req.question),
                              answer=answer, hit_ids=hit_ids)

        get_client().set_current_trace_io(input=req.question, output=answer)
        get_client().update_current_span(input=req.question, output=answer)
    return {"answer": answer, "hits": state.get("hits", []),
            "tool_call": state.get("tool_call"), "guard": guard_reasons or None}


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")
