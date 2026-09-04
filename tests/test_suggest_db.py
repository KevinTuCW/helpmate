"""The question bank reads the audit trail, so it inherits the audit trail's
tenant boundary. A missing `tenant_id = %s` here would show one tenant what
another tenant's customers are asking — a leak with no error message.
"""
from contextlib import contextmanager

from helpmate import db


class _FakeCursor:
    def __init__(self, rows, log):
        self._rows, self._log = rows, log

    def execute(self, sql, params):
        self._log.append((" ".join(sql.split()), params))

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, rows, log):
        self._rows, self._log = rows, log

    def cursor(self):
        return _FakeCursor(self._rows, self._log)


def _patch_conn(monkeypatch, rows):
    log: list = []

    @contextmanager
    def fake_conn():
        yield _FakeConn(rows, log)

    monkeypatch.setattr(db, "_conn", fake_conn)
    return log


def test_top_questions_scopes_to_the_tenant_and_returns_plain_strings(monkeypatch):
    log = _patch_conn(monkeypatch, [("限飞区怎么解禁", 9), ("保修范围", 4)])
    got = db.top_questions("dji", days=7, limit=4)
    assert got == ["限飞区怎么解禁", "保修范围"]
    sql, params = log[0]
    assert "tenant_id = %s" in sql
    assert params == ("dji", 7, 4)


def test_top_questions_ignores_blocked_turns(monkeypatch):
    log = _patch_conn(monkeypatch, [])
    db.top_questions("dji")
    sql, _ = log[0]
    assert "decision IN ('retrieve', 'act')" in sql


def test_search_questions_binds_a_substring_pattern_and_the_tenant(monkeypatch):
    log = _patch_conn(monkeypatch, [("限飞区怎么解禁",)])
    got = db.search_questions("限飞", "dji", limit=5)
    assert got == ["限飞区怎么解禁"]
    sql, params = log[0]
    assert "ILIKE" in sql and "tenant_id = %s" in sql
    assert params == ("dji", "%限飞%", 5)


def test_search_questions_escapes_wildcards_in_user_input(monkeypatch):
    # A bare "%" from the user must not turn into "match everything".
    log = _patch_conn(monkeypatch, [])
    db.search_questions("100%", "dji")
    _, params = log[0]
    assert params[1] == r"%100\%%"


# --- Chinese FTS -------------------------------------------------------------
# Documents and queries must go through the same segmentation. If either side
# skips it the index fills up with surrogates nothing ever searches for, and FTS
# silently returns nothing — the exact failure this replaced.

def test_insert_chunk_row_writes_a_segmented_tsvector(monkeypatch):
    log = _patch_conn(monkeypatch, [])
    db.insert_chunk_row(1, {"chunk_index": 0, "content": "限飞区解禁",
                            "doc_type": "policy"})
    sql, params = log[0]
    assert "content_tsv" in sql and "to_tsvector('simple', %s)" in sql
    from helpmate.retrieve.segment import segment
    assert segment("限飞区解禁") in params


def test_fts_search_segments_the_query_before_binding(monkeypatch):
    from helpmate.retrieve.segment import segment_query
    log = _patch_conn(monkeypatch, [])
    db.fts_search("解禁", 5, "dji")
    _, params = log[0]
    assert segment_query("解禁") in params
    assert "解禁" not in params        # the raw term would match nothing
