import math
from helpmate.config import get_settings
from helpmate.providers import LocalHashingEmbedder


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


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
