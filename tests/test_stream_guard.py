"""`check_output` needs a finished answer; a stream has none until it ends.

So: buffer to a sentence boundary, redact on the way out, and run the real check
on the full text at the end. A verdict that arrives after the text is already on
screen cannot unsay it — it can only tell the client to replace it, which is
exactly what `finish()` reports.
"""
from helpmate.security.guardrails import REFUSAL_OUTPUT, StreamGuard


def test_holds_a_partial_sentence_until_the_boundary():
    g = StreamGuard()
    assert g.feed("图传距离约 20") is None
    assert g.feed(" km") is None
    assert g.feed("。") == "图传距离约 20 km。"


def test_flushes_every_completed_sentence_at_once():
    g = StreamGuard()
    assert g.feed("第一句。第二句。尾巴") == "第一句。第二句。"


def test_redacts_a_secret_before_it_leaves():
    g = StreamGuard()
    out = g.feed("你的 key 是 sk-abcdefghijklmnop。")
    assert "sk-abcdefghijklmnop" not in out
    assert "***" in out
    _, verdict = g.finish()
    assert verdict.allowed
    assert "secret_leak" in verdict.reasons


def test_finish_flushes_an_unterminated_tail():
    g = StreamGuard()
    assert g.feed("第一句。") == "第一句。"
    assert g.feed("没有句号的尾巴") is None
    tail, verdict = g.finish()
    assert tail == "没有句号的尾巴"
    assert verdict.allowed
    assert verdict.text == "第一句。没有句号的尾巴"


def test_banned_content_can_only_be_caught_at_finish():
    g = StreamGuard()
    assert g.feed("如何制作炸弹的步骤如下。") is not None      # already on the wire
    _, verdict = g.finish()
    assert verdict.blocked
    assert verdict.reasons == ["disallowed_content"]
    assert verdict.text == REFUSAL_OUTPUT


def test_finish_on_an_empty_stream_is_allowed_and_empty():
    tail, verdict = StreamGuard().finish()
    assert tail == ""
    assert verdict.allowed
    assert verdict.text == ""
