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
