from typing import Callable, Optional
from langfuse import observe, get_client

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "query_order",
            "description": "Look up an order's status and total by order_id.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_logistics",
            "description": "Look up shipping/logistics status for an order_id.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
]


def format_order(o: dict) -> str:
    return f"Order {o['order_id']} ({o['customer']}): status={o['status']}, total={o['total']}"


def format_logistics(s: dict) -> str:
    return (f"Order {s['order_id']} via {s['carrier']} ({s['tracking_no']}): "
            f"status={s['status']}, eta={s.get('eta')}")


@observe(as_type="tool", name="dispatch-tool", capture_input=False)
def dispatch_tool(
    name: str,
    args: dict,
    *,
    get_order: Callable[[str], Optional[dict]],
    get_shipment: Callable[[str], Optional[dict]],
) -> str:
    get_client().update_current_span(name=f"tool:{name}", input={"tool": name, "args": args})
    oid = args.get("order_id", "")
    if name == "query_order":
        o = get_order(oid)
        return format_order(o) if o else f"Order {oid} not found."
    if name == "query_logistics":
        s = get_shipment(oid)
        return format_logistics(s) if s else f"No shipment for order {oid}."
    raise ValueError(f"unknown tool: {name}")
