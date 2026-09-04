import helpmate.obs  # noqa: F401  -- initializes Langfuse before any OpenAI client
import asyncio
import json
import logging
import queue
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
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
from helpmate.security import (check_input, check_output, redact_pii, StreamGuard,
                               REFUSAL_INPUT, REFUSAL_OUTPUT)
from helpmate.session import rewrite_query
from helpmate.ops import should_sample
from helpmate.suggest import followups, hot_questions, match_questions

WEB = Path(__file__).resolve().parents[2] / "web"
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Name the database on the first line of the log.

    Not a gate — the app still starts if this fails. It exists because the wrong
    database is invisible: an exported DATABASE_URL from another project
    outranks `.env`, and every query then fails on a table that "should" be
    there. Seeing `nexus@localhost:5432` where `helpmate@…` was expected turns
    twenty minutes of debugging into one glance.
    """
    # uvicorn.error is the logger uvicorn configures at INFO; ours would be
    # filtered out by the root logger's default WARNING level.
    try:
        logging.getLogger("uvicorn.error").info("database: %s", db.describe())
    except Exception as exc:
        logging.getLogger("uvicorn.error").warning(
            "database: unreachable (%s)", exc.__class__.__name__)
    yield


app = FastAPI(title="helpmate", lifespan=lifespan)


class IngestReq(BaseModel):
    source: str
    title: str
    text: str


class ChatReq(BaseModel):
    question: str
    session_id: str | None = None
    # No tenant_id here on purpose: identity comes from the credential, never
    # from the request body. A caller must not be able to name its own tenant.


class FollowupReq(BaseModel):
    question: str
    answer: str
    hit_titles: list[str] = []
    session_id: str | None = None


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _cite_meta(hits: list[dict]) -> list[dict]:
    """Citation metadata for the UI: titles and links, never the chunk text.

    `/chat` hands the browser whole chunks; a widget embedded on a public page
    has no business receiving the corpus verbatim.
    """
    return [{"n": i + 1,
             "title": h.get("doc_title") or h.get("section_title") or "",
             "section": h.get("section_title") or "",
             "url": h.get("source_url") or ""}
            for i, h in enumerate(hits)]


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


def _persist_turn(*, tenant: str, req: "ChatReq", decision: str,
                  tool_name: Optional[str], guard_reasons: list[str],
                  answer: str, hits: list[dict], remember: bool = True) -> None:
    """Every side effect a finished turn owes the system, in one place.

    Both `/chat` and `/chat/stream` call this. Duplicating it would eventually
    mean one path stops writing the audit row — a governance blind spot that no
    test would notice unless it is pinned here.

    `remember=False` for a blocked input: it still gets audited, but an injection
    attempt must not enter the multi-turn memory that rewrites later queries.
    """
    s = get_settings()
    db.write_audit(tenant_id=tenant, session_id=req.session_id,
                   question=redact_pii(req.question), decision=decision,
                   tool_call=tool_name, guard=guard_reasons, answer=answer)
    if remember and req.session_id:
        db.append_turn(req.session_id, "user", req.question)
        db.append_turn(req.session_id, "assistant", answer)
    if should_sample(req.session_id or req.question, s.online_sample_rate):
        db.capture_sample(tenant_id=tenant, session_id=req.session_id,
                          question=redact_pii(req.question), answer=answer,
                          hit_ids=[h.get("chunk_id") for h in hits])


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
                _persist_turn(tenant=tenant, req=req, decision="blocked_input",
                              tool_name=None, guard_reasons=gin.reasons,
                              answer="", hits=[], remember=False)
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

        # governance + multi-turn + ops sampling, shared with the streaming path
        _persist_turn(tenant=tenant, req=req, decision=decision,
                      tool_name=(state.get("tool_call") or {}).get("name"),
                      guard_reasons=guard_reasons, answer=answer,
                      hits=state.get("hits", []))

        get_client().set_current_trace_io(input=req.question, output=answer)
        get_client().update_current_span(input=req.question, output=answer)
    return {"answer": answer, "hits": state.get("hits", []),
            "tool_call": state.get("tool_call"), "guard": guard_reasons or None}


def _produce_turn(req: ChatReq, principal: Principal, out: queue.Queue) -> None:
    """Run one streamed turn to completion, pushing SSE frames into `out`.

    Deliberately *not* a generator. Langfuse spans ride on OpenTelemetry's
    context, which lives in a contextvar; Starlette drives a sync generator with
    one threadpool hop per `next()`, so a `with` block wrapped around a `yield`
    is entered and exited against different copies of that context — the span
    detaches wrongly and the streamed turn loses its trace nesting. Keeping every
    suspension point out of this function fixes that: it runs start to finish on
    one thread, and the async side below only ferries finished frames.

    Every exit path — normal end, guardrail block, upstream failure, client
    hangup — goes through the `finally`, so the audit row is written exactly once
    and the reader is always released by the sentinel.
    """
    s = get_settings()
    tenant = principal.tenant_id
    acc = {"decision": "retrieve", "tool": None, "hits": [], "guard": [],
           "answer": "", "remember": True, "persisted": False}

    def persist():
        if acc["persisted"]:
            return
        acc["persisted"] = True
        _persist_turn(tenant=tenant, req=req, decision=acc["decision"],
                      tool_name=acc["tool"], guard_reasons=acc["guard"],
                      answer=acc["answer"], hits=acc["hits"],
                      remember=acc["remember"])

    try:
        attrs = {"tags": ["chat", "stream"]}
        if req.session_id:
            attrs["session_id"] = req.session_id
        with propagate_attributes(**attrs), \
                get_client().start_as_current_observation(name="chat-stream-response"):
            get_client().set_current_trace_io(input=req.question)

            # input guardrail — refuse before any model call, same as /chat
            if s.guardrails_enabled:
                gin = check_input(req.question)
                if gin.blocked:
                    acc.update(decision="blocked_input", guard=gin.reasons,
                               answer=REFUSAL_INPUT, remember=False)
                    out.put(_sse("token", {"text": REFUSAL_INPUT}))
                    out.put(_sse("done", {"hits": [], "tool_call": None,
                                          "guard": gin.reasons}))
                    get_client().set_current_trace_io(input=req.question,
                                                      output=REFUSAL_INPUT)
                    return

            history = (db.recent_turns(req.session_id, s.session_history_turns)
                       if req.session_id else [])
            runner = build_graph(
                retriever=lambda q: hybrid_retrieve(q, tenant_id=tenant),
                # Order lookups stay bound to the authenticated principal here
                # too — the streaming path is the same data path.
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
            guard = StreamGuard()
            for ev in runner.stream(
                    req.question,
                    retrieval_query=rewrite_query(req.question, history)):
                if "stage" in ev:
                    out.put(_sse("stage", {"stage": ev["stage"]}))
                elif "hits" in ev:
                    acc["hits"] = ev["hits"]
                    out.put(_sse("stage", {"stage": "retrieved",
                                           "count": len(ev["hits"])}))
                elif "token" in ev:
                    text = (guard.feed(ev["token"]) if s.guardrails_enabled
                            else ev["token"])
                    if text:
                        out.put(_sse("token", {"text": text}))
                elif "state" in ev:
                    tool_call = ev["state"].get("tool_call")
                    acc["tool"] = (tool_call or {}).get("name")
                    acc["decision"] = "act" if tool_call else "retrieve"
                    acc["answer"] = ev["state"].get("answer", "")

            if s.guardrails_enabled:
                tail, verdict = guard.finish()
                if tail:
                    out.put(_sse("token", {"text": tail}))
                acc["guard"] = verdict.reasons
                acc["answer"] = verdict.text
                if verdict.blocked:
                    acc["decision"] = "blocked_output"
                    out.put(_sse("replace", {"text": verdict.text}))

            out.put(_sse("done", {"hits": _cite_meta(acc["hits"]),
                                  "tool_call": acc["tool"],
                                  "guard": acc["guard"] or None}))
            get_client().set_current_trace_io(input=req.question,
                                              output=acc["answer"])
    except Exception:
        out.put(_sse("error", {"message": "stream failed"}))
    finally:
        try:
            persist()
        except Exception:
            # The answer is already delivered; failing the response now helps
            # nobody. But a silently lost audit row is exactly the governance
            # gap this layer exists to prevent, so it goes to the log loudly.
            log.exception("persisting a streamed turn failed")
        finally:
            # Own finally: the reader blocks on get() until this arrives, so a
            # dead database must not turn into a hung request.
            out.put(None)


async def _chat_events(req: ChatReq, principal: Principal):
    """Ferry frames from the worker thread to the client. No business logic here."""
    out: queue.Queue = queue.Queue()
    worker = asyncio.get_running_loop().run_in_executor(
        None, _produce_turn, req, principal, out)
    try:
        while True:
            frame = await asyncio.to_thread(out.get)
            if frame is None:
                break
            yield frame
    finally:
        await worker          # surface a worker crash instead of swallowing it


@app.post("/chat/stream")
def chat_stream(req: ChatReq, principal: Principal = Depends(require_principal)):
    return StreamingResponse(
        _chat_events(req, principal),
        media_type="text/event-stream",
        # Buffering proxies would hold the whole stream and defeat the point.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/suggest/hot")
def suggest_hot(principal: Principal = Depends(require_principal)):
    return {"questions": hot_questions(principal.tenant_id)}


@app.get("/suggest/match")
def suggest_match(q: str = "", principal: Principal = Depends(require_principal)):
    return {"questions": match_questions(q, principal.tenant_id)}


@app.post("/suggest/followups")
def suggest_followups(req: FollowupReq,
                      principal: Principal = Depends(require_principal)):
    return {"questions": followups(req.question, req.answer, req.hit_titles,
                                   OpenAILLM())}


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


# Mounted last: a mount swallows every path beneath it, so it must not be
# declared before the API routes.
app.mount("/widget", StaticFiles(directory=WEB / "widget"), name="widget")
