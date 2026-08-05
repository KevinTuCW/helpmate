from typing import Callable, Optional, TypedDict
from langgraph.graph import StateGraph, END
from helpmate.retrieve import format_context
from helpmate.tools import TOOL_SCHEMAS

PROMPT = (
    "You are a support assistant. Answer using ONLY the context below. "
    "If a chunk is cited like [1], keep the citation. "
    "If the context is insufficient, say you don't have enough information.\n\n"
    "Context:\n{context}\n\nQuestion: {question}\nAnswer:"
)


class ChatState(TypedDict, total=False):
    question: str
    retrieval_query: Optional[str]   # history-enriched query for retrieval; falls back to question
    tool_call: Optional[dict]
    hits: list[dict]
    context: str
    answer: str


def build_prompt(question: str, context: str) -> str:
    return PROMPT.format(context=context, question=question)


def build_graph(
    *,
    retriever: Callable[[str], list[dict]],
    tool_dispatch: Callable[[str, dict], str],
    llm,
) -> Callable[[str], ChatState]:
    def route(state: ChatState) -> ChatState:
        return {"tool_call": llm.select_tool(state["question"], TOOL_SCHEMAS)}

    def act(state: ChatState) -> ChatState:
        call = state["tool_call"]
        return {"context": tool_dispatch(call["name"], call["args"])}

    def retrieve(state: ChatState) -> ChatState:
        hits = retriever(state.get("retrieval_query") or state["question"])
        return {"hits": hits, "context": format_context(hits)}

    def generate(state: ChatState) -> ChatState:
        return {"answer": llm.complete(build_prompt(state["question"], state["context"]))}

    def decide(state: ChatState) -> str:
        return "act" if state.get("tool_call") else "retrieve"

    g = StateGraph(ChatState)
    g.add_node("route", route)
    g.add_node("act", act)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.set_entry_point("route")
    g.add_conditional_edges("route", decide, {"act": "act", "retrieve": "retrieve"})
    g.add_edge("act", "generate")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    compiled = g.compile()

    def run(question: str, retrieval_query: Optional[str] = None) -> ChatState:
        return compiled.invoke({"question": question, "retrieval_query": retrieval_query})

    return run
