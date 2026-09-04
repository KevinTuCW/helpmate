"""Suggestions are an enhancement, never a dependency: every entry point here
degrades to a shorter list (or an empty one) instead of raising, because a dead
suggestion query must not take the conversation down with it.
"""
import pytest

from helpmate import suggest


def test_hot_questions_backfills_seeds_on_a_cold_start(monkeypatch):
    monkeypatch.setattr(suggest.db, "top_questions", lambda *a, **k: [])
    assert suggest.hot_questions("dji", limit=4) == suggest.SEED_QUESTIONS[:4]


def test_hot_questions_put_real_traffic_first(monkeypatch):
    monkeypatch.setattr(suggest.db, "top_questions", lambda *a, **k: ["炸机能保修吗"])
    got = suggest.hot_questions("dji", limit=3)
    assert got[0] == "炸机能保修吗"
    assert len(got) == 3


def test_hot_questions_survive_a_dead_database(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(suggest.db, "top_questions", boom)
    assert suggest.hot_questions("dji", limit=2) == suggest.SEED_QUESTIONS[:2]


def test_match_needs_two_characters_before_touching_the_db(monkeypatch):
    def must_not_run(*a, **k):
        pytest.fail("one character must not trigger a query")

    monkeypatch.setattr(suggest.db, "search_questions", must_not_run)
    assert suggest.match_questions("限", "dji") == []
    assert suggest.match_questions("  ", "dji") == []


def test_match_falls_back_to_seed_substrings(monkeypatch):
    monkeypatch.setattr(suggest.db, "search_questions", lambda *a, **k: [])
    got = suggest.match_questions("限飞", "dji")
    assert got == ["限飞区怎么申请解禁"]


def test_match_dedupes_history_against_seeds(monkeypatch):
    monkeypatch.setattr(suggest.db, "search_questions",
                        lambda *a, **k: ["限飞区怎么申请解禁"])
    assert suggest.match_questions("限飞", "dji") == ["限飞区怎么申请解禁"]


def test_match_survives_a_dead_database(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(suggest.db, "search_questions", boom)
    assert suggest.match_questions("限飞", "dji") == ["限飞区怎么申请解禁"]


class _LLM:
    """Stand-in for OpenAILLM: replays a canned small-model completion."""

    def __init__(self, raw):
        self._raw = raw

    def complete_small(self, prompt):
        return self._raw


def test_followups_strip_numbering_and_drop_overlong_lines():
    raw = ("1. 解禁审核要多久\n"
           "2. 授权区和禁飞区有什么区别\n"
           "3. 这是一个非常非常冗长根本不像用户会问出口的问题所以应该被丢掉\n")
    got = suggest.followups("限飞区怎么解禁", "需要提交申请。", ["限飞政策"], _LLM(raw))
    assert got == ["解禁审核要多久", "授权区和禁飞区有什么区别"]


def test_followups_drop_duplicates_and_echoes_of_the_question():
    raw = "限飞区怎么解禁\n解禁要多久\n解禁要多久\n"
    got = suggest.followups("限飞区怎么解禁", "需要提交申请。", [], _LLM(raw))
    assert got == ["解禁要多久"]


def test_followups_drop_preamble_lines():
    raw = "以下是三个问题：\n解禁要多久\n- 需要什么材料\n"
    got = suggest.followups("限飞区怎么解禁", "需要提交申请。", [], _LLM(raw))
    assert got == ["解禁要多久", "需要什么材料"]


def test_followups_cap_at_three():
    raw = "问题一啊\n问题二啊\n问题三啊\n问题四啊\n"
    assert len(suggest.followups("q啊啊", "a。", [], _LLM(raw))) == 3


def test_followups_return_empty_when_the_model_fails():
    class Boom:
        def complete_small(self, prompt):
            raise RuntimeError("upstream 500")

    assert suggest.followups("问题啊", "答案。", [], Boom()) == []


def test_followups_skip_an_empty_answer():
    assert suggest.followups("问题啊", "   ", [], _LLM("甲问题啊\n乙问题啊\n丙问题啊")) == []
