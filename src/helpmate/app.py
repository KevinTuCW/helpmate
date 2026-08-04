from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

from helpmate.config import get_settings
from helpmate.ingest import chunk_text
from helpmate import db
from helpmate.tools import dispatch_tool
from helpmate.providers import OpenAIEmbedder, OpenAILLM
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
    embedder = OpenAIEmbedder()
    doc_id = db.insert_document(req.source, req.title)
    chunks = chunk_text(req.text)
    for ch in chunks:
        db.insert_chunk(doc_id, ch["chunk_index"], ch["content"], embedder.embed(ch["content"]))
    return {"document_id": doc_id, "chunks": len(chunks)}


@app.post("/chat")
def chat(req: ChatReq):
    settings = get_settings()
    embedder = OpenAIEmbedder()
    run = build_graph(
        retriever=lambda q: db.search(embedder.embed(q), settings.top_k),
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
