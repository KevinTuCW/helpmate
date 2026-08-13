"""Retrieval must be scoped to the caller's tenant — and the params must line up.

The regression these lock down: the tenant filter is stitched into the SQL
string, so adding it shifted every positional parameter after it. `dense_search`
kept passing the embedding first, which made Postgres hand `'public'` to the
`::vector` cast ("invalid input syntax for type vector"). Asserting the exact
param tuple is the point — a placeholder-order bug is invisible to any test that
only checks the returned rows.
"""
from contextlib import contextmanager

from helpmate import db

_ROW = (1, "DJI Care 随心换覆盖进水。", "保障范围",
        "https://example.com/care", "DJI Care FAQ", "faq")


class _FakeCursor:
    """Records the SQL + params it was handed and replays a canned row."""

    def __init__(self, log):
        self._log = log

    def execute(self, sql, params):
        self._log.append((" ".join(sql.split()), params))

    def fetchall(self):
        return [_ROW]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, log):
        self._log = log

    def cursor(self):
        return _FakeCursor(self._log)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_conn(monkeypatch):
    log: list = []

    @contextmanager
    def fake_conn():
        yield _FakeConn(log)

    monkeypatch.setattr(db, "_conn", fake_conn)
    return log


def _param_at(sql: str, params: tuple, marker: str):
    """The param bound to the last %s placeholder before `marker`."""
    return params[sql[:sql.index(marker)].count("%s") - 1]


def test_dense_search_binds_the_vector_placeholder_to_the_embedding(monkeypatch):
    log = _patch_conn(monkeypatch)
    db.dense_search([0.1, 0.2, 0.3], 5, "dji")

    sql, params = log[0]
    assert "ch.tenant_id = %s" in sql
    assert params == ("dji", "[0.1, 0.2, 0.3]", 5)
    # What actually broke: the cast got the tenant string, not the vector.
    assert _param_at(sql, params, "::vector").startswith("[")


def test_dense_search_without_a_tenant_drops_the_filter_and_the_param(monkeypatch):
    log = _patch_conn(monkeypatch)
    db.dense_search([0.1, 0.2, 0.3], 5)

    sql, params = log[0]
    assert "tenant_id" not in sql
    assert params == ("[0.1, 0.2, 0.3]", 5)


def test_fts_search_repeats_the_query_around_the_tenant_param(monkeypatch):
    log = _patch_conn(monkeypatch)
    db.fts_search("进水 保修", 5, "dji")

    sql, params = log[0]
    assert "ch.tenant_id = %s" in sql
    # websearch_to_tsquery appears twice (filter + rank), tenant sits between.
    assert params == ("进水 保修", "dji", "进水 保修", 5)


def test_fts_search_without_a_tenant_drops_the_filter_and_the_param(monkeypatch):
    log = _patch_conn(monkeypatch)
    db.fts_search("进水 保修", 5)

    sql, params = log[0]
    assert "tenant_id" not in sql
    assert params == ("进水 保修", "进水 保修", 5)


def test_a_foreign_tenant_cannot_be_reached_through_retrieval(monkeypatch):
    """Every retrieval path carries the tenant into the WHERE clause; no code
    path returns chunks filtered only in Python after the fact."""
    log = _patch_conn(monkeypatch)
    db.dense_search([0.1], 5, "acme")
    db.fts_search("进水", 5, "acme")

    for sql, params in log:
        assert "ch.tenant_id = %s" in sql
        assert "acme" in params
