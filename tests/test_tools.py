from helpmate.tools import format_order, format_logistics, dispatch_tool, TOOL_SCHEMAS


def test_tool_schemas_expose_two_functions():
    names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    assert names == {"query_order", "query_logistics"}


def test_format_order_does_not_echo_customer_name():
    o = {"order_id": "A1001", "customer": "Alice", "status": "shipped", "total": 129.0}
    out = format_order(o)
    assert out == "Order A1001: status=shipped, total=129.0"
    assert "Alice" not in out


def test_format_logistics():
    s = {"order_id": "A1001", "carrier": "SF Express", "tracking_no": "SF7788123",
         "status": "in_transit", "eta": "2026-08-06"}
    out = format_logistics(s)
    assert "SF Express" in out and "SF7788123" in out and "in_transit" in out


def test_dispatch_query_order_found_and_missing():
    got = dispatch_tool(
        "query_order", {"order_id": "A1001"},
        get_order=lambda oid: {"order_id": oid, "customer": "Alice",
                               "status": "shipped", "total": 129.0},
        get_shipment=lambda oid: None,
    )
    assert "Order A1001" in got
    missing = dispatch_tool(
        "query_order", {"order_id": "X"},
        get_order=lambda oid: None, get_shipment=lambda oid: None,
    )
    assert missing == "Order X not found."


def test_dispatch_unknown_tool_raises():
    import pytest
    with pytest.raises(ValueError):
        dispatch_tool("nope", {}, get_order=lambda o: None, get_shipment=lambda o: None)
