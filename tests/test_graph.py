from helpmate.graph import build_graph, build_prompt


def test_build_prompt_embeds_context_and_question():
    p = build_prompt("How long do cats sleep?", "[1] (Cat FAQ) Cats sleep 15h.")
    assert "How long do cats sleep?" in p
    assert "[1] (Cat FAQ) Cats sleep 15h." in p


class ToolLLM:
    def select_tool(self, q, schemas):
        return {"name": "query_order", "args": {"order_id": "A1001"}}
    def complete(self, prompt):
        assert "Order A1001" in prompt  # tool result reached the LLM
        return "Your order A1001 has shipped."


class RagLLM:
    def select_tool(self, q, schemas):
        return None
    def complete(self, prompt):
        assert "Cats sleep 15h." in prompt  # RAG context reached the LLM
        return "About 15 hours [1]."


def test_tool_path_uses_function_calling():
    run = build_graph(
        retriever=lambda q: [],
        tool_dispatch=lambda name, args: f"Order {args['order_id']} has shipped.",
        llm=ToolLLM(),
    )
    state = run("Where is my order A1001?")
    assert state["answer"] == "Your order A1001 has shipped."


def test_rag_path_when_no_tool_selected():
    run = build_graph(
        retriever=lambda q: [{"content": "Cats sleep 15h.", "title": "Cat FAQ"}],
        tool_dispatch=lambda name, args: "unused",
        llm=RagLLM(),
    )
    state = run("How long do cats sleep?")
    assert state["answer"] == "About 15 hours [1]."
    assert state["hits"] == [{"content": "Cats sleep 15h.", "title": "Cat FAQ"}]


class StreamLLM:
    def select_tool(self, q, schemas):
        return None

    def complete(self, prompt):
        raise AssertionError("the streaming path must not call the blocking complete()")

    def complete_stream(self, prompt):
        assert "Cats sleep 15h." in prompt
        yield "About "
        yield "15 hours [1]."


def test_run_stream_reports_stages_hits_tokens_then_final_state():
    runner = build_graph(
        retriever=lambda q: [{"content": "Cats sleep 15h.", "title": "Cat FAQ"}],
        tool_dispatch=lambda name, args: "unused",
        llm=StreamLLM(),
    )
    events = list(runner.stream("How long do cats sleep?"))

    assert [e["stage"] for e in events if "stage" in e] == ["route", "retrieve", "generate"]
    assert [e["hits"] for e in events if "hits" in e] == [
        [{"content": "Cats sleep 15h.", "title": "Cat FAQ"}]]
    assert "".join(e["token"] for e in events if "token" in e) == "About 15 hours [1]."
    final = [e["state"] for e in events if "state" in e][-1]
    assert final["answer"] == "About 15 hours [1]."
    assert final["tool_call"] is None


def test_the_runner_is_still_directly_callable_for_the_blocking_path():
    runner = build_graph(
        retriever=lambda q: [{"content": "Cats sleep 15h.", "title": "Cat FAQ"}],
        tool_dispatch=lambda name, args: "unused",
        llm=RagLLM(),
    )
    assert runner("How long do cats sleep?")["answer"] == "About 15 hours [1]."
