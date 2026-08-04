from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

from helpmate.config import get_settings
from helpmate import db
from helpmate.tools import dispatch_tool
from helpmate.providers import get_embedder, OpenAILLM
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
    # v2: batch corpus ingestion runs via ingest.pipeline (see scripts/).
    # The HTTP ingest endpoint is re-wired with embeddings in phase 2.
    raise HTTPException(status_code=501, detail="use ingest.pipeline; endpoint rewired in phase 2")


@app.post("/chat")
def chat(req: ChatReq):
    settings = get_settings()
    embedder = get_embedder()
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
