"""Order lookups must be bound to the caller — the tool path is a data path.

The regression these lock down: `query_order` used to accept any order_id, so
reciting a stranger's number returned their status (and name). Guardrail regexes
catch someone *asking* for "别人的订单"; they cannot catch a plain order id.
"""
from helpmate import db


class _FakeCursor:
    """Records the SQL + params it was handed and replays a canned row."""

    def __init__(self, row, log):
        self._row = row
        self._log = log

    def execute(self, sql, params):
        self._log.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self._row

    def fetchall(self):
        return [self._row] if self._row else []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, row, log):
        self._row = row
        self._log = log

    def cursor(self):
        return _FakeCursor(self._row, self._log)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_conn(monkeypatch, row):
    from contextlib import contextmanager
    log: list = []

    @contextmanager
    def fake_conn():
        yield _FakeConn(row, log)

    monkeypatch.setattr(db, "_conn", fake_conn)
    return log


def test_get_order_filters_by_tenant_and_customer(monkeypatch):
    log = _patch_conn(monkeypatch, ("A1001", "Alice", "shipped", 129.0))
    got = db.get_order("A1001", tenant_id="dji", customer_id="Alice")
    assert got["order_id"] == "A1001"
    sql, params = log[0]
    assert "tenant_id = %s" in sql and "customer_id = %s" in sql
    assert params == ("A1001", "dji", "Alice")


def test_get_order_without_a_bound_customer_never_touches_the_db(monkeypatch):
    log = _patch_conn(monkeypatch, ("A1001", "Alice", "shipped", 129.0))
    assert db.get_order("A1001", tenant_id="dji", customer_id=None) is None
    assert log == []          # denied before any query is issued


def test_foreign_order_is_indistinguishable_from_a_missing_one(monkeypatch):
    # The DB returns no row because the WHERE clause excludes it; the caller
    # gets the same None a nonexistent order produces — no enumeration signal.
    _patch_conn(monkeypatch, None)
    assert db.get_order("A1002", tenant_id="dji", customer_id="Alice") is None


def test_get_shipment_authorizes_through_the_orders_table(monkeypatch):
    log = _patch_conn(monkeypatch, ("A1001", "SF", "SF77", "in_transit", None))
    got = db.get_shipment("A1001", tenant_id="dji", customer_id="Alice")
    assert got["carrier"] == "SF"
    sql, params = log[0]
    assert "JOIN orders" in sql and "o.customer_id = %s" in sql
    assert params == ("A1001", "dji", "Alice")


def test_get_shipment_without_a_bound_customer_is_denied(monkeypatch):
    log = _patch_conn(monkeypatch, ("A1001", "SF", "SF77", "in_transit", None))
    assert db.get_shipment("A1001", tenant_id="dji", customer_id=None) is None
    assert log == []


def test_ingest_backfill_can_be_scoped_to_one_document(monkeypatch):
    """/ingest must embed the chunks it just wrote, not every pending chunk
    in the database (which spans other tenants)."""
    log = _patch_conn(monkeypatch, None)

    db.fetch_unembedded(32, document_id=7)
    sql, params = log[0]
    assert "document_id = %s" in sql
    assert params == (7, 32)

    log.clear()
    db.fetch_unembedded(32)
    sql, params = log[0]
    assert "document_id" not in sql
    assert params == (32,)
