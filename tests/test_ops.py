from helpmate.ops import should_sample


def test_rate_bounds():
    assert should_sample("anything", 0) is False
    assert should_sample("anything", 100) is True


def test_deterministic_per_key():
    assert should_sample("sess-1", 50) == should_sample("sess-1", 50)


def test_rate_roughly_matches():
    keys = [f"k{i}" for i in range(1000)]
    hits = sum(should_sample(k, 10) for k in keys)
    assert 50 <= hits <= 150   # ~10% of 1000, generous bounds
