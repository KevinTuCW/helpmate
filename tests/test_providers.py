import math
import types
import helpmate.providers as providers
from helpmate.config import get_settings
from helpmate.providers import LocalHashingEmbedder, OpenAILLM


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


class _RecordingClient:
    """Captures the kwargs of the last chat.completions.create call."""

    def __init__(self) -> None:
        self.calls = []
        reply = types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(tool_calls=None, content=""))])
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(
            create=lambda **kw: (self.calls.append(kw), reply)[1]))


def _patched_llm(monkeypatch):
    """OpenAILLM with both clients replaced, so no network call is made."""
    clients = []

    def fake_client(base_url=None, api_key=None):
        c = _RecordingClient()
        c.base_url, c.api_key = base_url, api_key
        clients.append(c)
        return c

    monkeypatch.setattr(providers, "_client", fake_client)
    return OpenAILLM(), clients


def test_select_tool_uses_the_router_model_not_the_answer_model(monkeypatch):
    llm, clients = _patched_llm(monkeypatch)
    answer_client, router_client = clients
    s = get_settings()

    llm.select_tool("我的订单 A1001 到哪了？", [{"type": "function"}])

    assert not answer_client.calls              # the answer model stays out of routing
    kw = router_client.calls[0]
    assert kw["model"] == s.router_model
    assert router_client.base_url == s.router_base_url()


def test_select_tool_prompts_against_inventing_an_order_id(monkeypatch):
    # Without this rule a small router fabricates order_id="order_id" on KB
    # questions and misroutes them; the golden set drops from 1.00 to 0.98.
    llm, clients = _patched_llm(monkeypatch)
    llm.select_tool("图传方案是什么？", [{"type": "function"}])

    msgs = clients[1].calls[0]["messages"]
    assert msgs[0]["role"] == "system"
    assert "invent" in msgs[0]["content"].lower()
    assert msgs[1] == {"role": "user", "content": "图传方案是什么？"}


def test_thinking_is_disabled_only_for_siliconflow(monkeypatch):
    # enable_thinking is a SiliconFlow extension; z.ai rejects the unknown field.
    llm, clients = _patched_llm(monkeypatch)
    llm._router_provider = "siliconflow"
    llm.select_tool("q", [])
    assert clients[1].calls[-1]["extra_body"] == {"enable_thinking": False}

    llm._router_provider = "llm"
    llm.select_tool("q", [])
    assert clients[1].calls[-1]["extra_body"] is None


def test_local_embedder_is_deterministic_and_normalized(monkeypatch):
    monkeypatch.setattr(get_settings(), "embed_dim", 256, raising=False)
    e = LocalHashingEmbedder()
    e._dim = 64  # keep the vector small for the test
    v1 = e.embed("refund policy details")
    v2 = e.embed("refund policy details")
    assert v1 == v2                                   # deterministic
    assert abs(math.sqrt(sum(x * x for x in v1)) - 1.0) < 1e-9  # L2-normalized


def test_local_embedder_overlap_beats_disjoint():
    e = LocalHashingEmbedder()
    e._dim = 512
    q = e.embed("what is the refund policy")
    related = e.embed("our refund policy allows returns")
    unrelated = e.embed("cats sleep fifteen hours")
    assert _cos(q, related) > _cos(q, unrelated)
