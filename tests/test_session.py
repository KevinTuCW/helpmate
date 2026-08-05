from helpmate.session import needs_context, rewrite_query


def test_needs_context_on_anaphora_and_short():
    assert needs_context("它的续航呢")
    assert needs_context("那款呢")
    assert needs_context("多少钱")            # short
    assert not needs_context("Mini 3 Pro 的最大水平飞行速度是多少")


def test_rewrite_prepends_prior_user_turn():
    history = [
        {"role": "user", "content": "Mini 3 Pro 续航多久"},
        {"role": "assistant", "content": "约 34 分钟"},
    ]
    assert rewrite_query("它防水吗", history) == "Mini 3 Pro 续航多久 它防水吗"


def test_rewrite_noop_without_history():
    assert rewrite_query("它防水吗", []) == "它防水吗"


def test_rewrite_noop_for_selfcontained_question():
    history = [{"role": "user", "content": "Mini 3 Pro 续航多久"}]
    q = "Air 3 的最大传输距离是多少"
    assert rewrite_query(q, history) == q


def test_rewrite_uses_only_user_turns_and_caps():
    history = [
        {"role": "user", "content": "A"},
        {"role": "assistant", "content": "ignored"},
        {"role": "user", "content": "B"},
    ]
    assert rewrite_query("它呢", history, max_turns=2) == "A B 它呢"
    assert rewrite_query("它呢", history, max_turns=1) == "B 它呢"
