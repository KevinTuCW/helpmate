from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

from helpmate import db
from helpmate.tools import dispatch_tool
from helpmate.providers import OpenAILLM
from helpmate.retrieve.embed import get_embedder
from helpmate.retrieve.hybrid import hybrid_retrieve
from helpmate.ingest.pipeline import ingest_source
from helpmate.graph import build_graph

app = FastAPI(title="helpmate")
WEB = Path(__file__).resolve().parents[2] / "web"


class IngestReq(BaseModel):
    source: str
    title: str
    text: str


class ChatReq(BaseModel):
    question: str


@app.post("/ingest")
def ingest(req: IngestReq):
    r = ingest_source(kind="html", path_or_html=req.text,
                      meta={"source_url": req.source, "title": req.title,
                            "doc_type": "faq", "product": None, "lang": "zh"})
    embedder = get_embedder()
    while True:
        rows = db.fetch_unembedded(32)
        if not rows:
            break
        vecs = embedder.embed_batch([c for _, c in rows])
        for (cid, _), v in zip(rows, vecs):
            db.update_embedding(cid, v)
    return r


@app.post("/chat")
def chat(req: ChatReq):
    run = build_graph(
        retriever=lambda q: hybrid_retrieve(q),
        tool_dispatch=lambda name, args: dispatch_tool(
            name, args, get_order=db.get_order, get_shipment=db.get_shipment
        ),
        llm=OpenAILLM(),
    )
    state = run(req.question)
    return {"answer": state["answer"], "hits": state.get("hits", []),
            "tool_call": state.get("tool_call")}


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")
