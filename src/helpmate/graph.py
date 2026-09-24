from dataclasses import dataclass, replace
from typing import Callable, Iterator, Optional, Sequence, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.config import get_stream_writer
from helpmate.retrieve import format_context
from helpmate.tools import TOOL_SCHEMAS
from helpmate.plugins import PluginReply, TurnPlugin

PROMPT = (
    "You are a support assistant. Answer using ONLY the context below. "
    "If a chunk is cited like [1], keep the citation. "
    "If the context is insufficient, say you don't have enough information.\n\n"
    "Context:\n{context}\n\nQuestion: {question}\nAnswer:"
)


class ChatState(TypedDict, total=False):
    question: str
    retrieval_query: Optional[str]   # history-enriched query for retrieval; falls back to question
    stream: bool                     # set by run_stream(); nodes stay silent when False
    tool_call: Optional[dict]
    hits: list[dict]
    context: str
    answer: str
    forced_plugin: Optional[str]
    plugin_reply: Optional[PluginReply]


def build_prompt(question: str, context: str) -> str:
    return PROMPT.format(context=context, question=question)


def _emit(state: ChatState, event: dict) -> None:
    """Push a progress event to the caller — only when running under `.stream()`.

    Stages are emitted *before* the node does its work. LangGraph's built-in
    "updates" stream fires after a node finishes, which would show the user
    "正在检索知识库" only once retrieval was already over.
    """
    if state.get("stream"):
        get_stream_writer()(event)


@dataclass
class GraphRunner:
    """One compiled graph, two ways to consume it.

    `runner(question)` blocks and returns the final state (what `/chat` uses).
    `runner.stream(question)` yields `{"stage"|"hits"|"token"|"state": …}` dicts
    in order (what `/chat/stream` uses). Callable so existing call sites and
    tests that did `run = build_graph(...); run(q)` keep working.
    """
    _run: Callable[..., ChatState]
    _stream: Callable[..., Iterator[dict]]
    graph: object = None

    def __call__(self, question: str, retrieval_query: Optional[str] = None,
                 forced_plugin: Optional[str] = None) -> ChatState:
        return self._run(question, retrieval_query, forced_plugin)

    def run(self, question: str, retrieval_query: Optional[str] = None,
            forced_plugin: Optional[str] = None) -> ChatState:
        return self._run(question, retrieval_query, forced_plugin)

    def stream(self, question: str,
               retrieval_query: Optional[str] = None,
               forced_plugin: Optional[str] = None) -> Iterator[dict]:
        return self._stream(question, retrieval_query, forced_plugin)


def build_graph(
    *,
    retriever: Callable[[str], list[dict]],
    tool_dispatch: Callable[[str, dict], str],
    llm,
    plugins: Sequence[TurnPlugin] = (),
    delegate: Optional[Callable[[str, dict], PluginReply]] = None,
) -> "GraphRunner":
    schemas = TOOL_SCHEMAS + [p.tool_schema for p in plugins]
    terminal_tools = {p.tool_name: p.name for p in plugins if p.terminal}

    def route(state: ChatState) -> ChatState:
        _emit(state, {"stage": "route"})
        return {"tool_call": llm.select_tool(state["question"], schemas)}

    def act(state: ChatState) -> ChatState:
        _emit(state, {"stage": "act"})
        call = state["tool_call"]
        return {"context": tool_dispatch(call["name"], call["args"])}

    def retrieve(state: ChatState) -> ChatState:
        _emit(state, {"stage": "retrieve"})
        hits = retriever(state.get("retrieval_query") or state["question"])
        _emit(state, {"hits": hits})
        return {"hits": hits, "context": format_context(hits)}

    def generate(state: ChatState) -> ChatState:
        _emit(state, {"stage": "generate"})
        prompt = build_prompt(state["question"], state["context"])
        if not state.get("stream"):
            return {"answer": llm.complete(prompt)}
        writer = get_stream_writer()
        parts: list[str] = []
        for delta in llm.complete_stream(prompt):
            parts.append(delta)
            writer({"token": delta})
        return {"answer": "".join(parts)}

    def delegate_node(state: ChatState) -> ChatState:
        _emit(state, {"stage": "delegate"})
        call = state.get("tool_call") or {}
        name = state.get("forced_plugin") or terminal_tools[call["name"]]
        reply = delegate(name, call.get("args") or {})
        if reply.handled and not reply.plugin_name:
            reply = replace(reply, plugin_name=name)
        out: ChatState = {"plugin_reply": reply}
        if reply.handled:
            out["answer"] = reply.answer
        return out

    def entry(state: ChatState) -> str:
        return "delegate" if state.get("forced_plugin") else "route"

    def after_delegate(state: ChatState) -> str:
        reply = state.get("plugin_reply")
        return "end" if (reply is not None and reply.handled) else "retrieve"

    def decide(state: ChatState) -> str:
        call = state.get("tool_call")
        if not call:
            return "retrieve"
        return "delegate" if call.get("name") in terminal_tools else "act"

    g = StateGraph(ChatState)
    g.add_node("route", route)
    g.add_node("act", act)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    if plugins and delegate is not None:
        g.add_node("delegate", delegate_node)
        g.set_conditional_entry_point(entry, {"delegate": "delegate", "route": "route"})
        g.add_conditional_edges("route", decide, {"act": "act", "retrieve": "retrieve",
                                                  "delegate": "delegate"})
        g.add_conditional_edges("delegate", after_delegate,
                                {"end": END, "retrieve": "retrieve"})
    else:
        g.set_entry_point("route")
        g.add_conditional_edges("route", decide, {"act": "act", "retrieve": "retrieve"})
    g.add_edge("act", "generate")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    compiled = g.compile()

    def run(question: str, retrieval_query: Optional[str] = None,
            forced_plugin: Optional[str] = None) -> ChatState:
        return compiled.invoke({"question": question,
                                "retrieval_query": retrieval_query,
                                "forced_plugin": forced_plugin})

    def run_stream(question: str,
                   retrieval_query: Optional[str] = None,
                   forced_plugin: Optional[str] = None) -> Iterator[dict]:
        final: ChatState = {"question": question}
        for mode, chunk in compiled.stream(
            {"question": question, "retrieval_query": retrieval_query,
             "forced_plugin": forced_plugin, "stream": True},
            stream_mode=["updates", "custom"],
        ):
            if mode == "custom":
                yield chunk                       # stage / hits / token
            else:
                for update in chunk.values():     # accumulate the node outputs
                    if update:
                        final.update(update)
        yield {"state": final}

    return GraphRunner(run, run_stream, compiled)
