"""Return Saver plugin adapter.

This is the only helpmate module that knows Return Saver's request and response
shape. Everywhere else talks in generic plugin terms.
"""
import logging
import re
import re
from typing import Callable, Optional, TYPE_CHECKING

import httpx

from helpmate.plugins import PluginReply, TurnContext, TurnPlugin

if TYPE_CHECKING:  # pragma: no cover
    from helpmate.config import Settings

log = logging.getLogger(__name__)

ESCAPE_PHRASES = frozenset({"还是要退", "还是要退货", "我还是要退", "我还是要退货"})
ORDER_ID_RE = re.compile(r"\bORD-[A-Za-z0-9-]+\b", re.IGNORECASE)
ORDER_ID_RE = re.compile(r"\bORD-[A-Za-z0-9-]+\b", re.IGNORECASE)

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "negotiate_return",
        "description": (
            "Handle a customer's return, refund, exchange or after-sales "
            "complaint about an order they received."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


def build_plugin(settings: "Settings", tenant_id: str) -> TurnPlugin:
    key = settings.return_saver_key_for(tenant_id)
    base = settings.return_saver_url
    timeout = settings.return_saver_timeout_s
    return TurnPlugin(
        name="return_saver",
        tool_schema=TOOL_SCHEMA,
        handle=lambda ctx: negotiate(ctx, base=base, key=key, timeout=timeout),
        actions={"accept": lambda principal, body: accept(
            body, base=base, key=settings.return_saver_key_for(principal.tenant_id),
            timeout=timeout)},
    )


def negotiate(ctx: TurnContext, *, base: str, key: str, timeout: float,
              post: Optional[Callable] = None) -> PluginReply:
    send = post or _default_post
    body = {"message": ctx.question,
            "want_return_anyway": _is_escape(ctx.question)}
    if ctx.customer_id:
        body["customer_id"] = ctx.customer_id
    if ctx.ext_session_id:
        body["session_id"] = ctx.ext_session_id
    order_match = ORDER_ID_RE.search(ctx.question or "")
    if order_match:
        body["confirm_order_id"] = order_match.group(0).upper()
    order_match = ORDER_ID_RE.search(ctx.question or "")
    if order_match:
        body["confirm_order_id"] = order_match.group(0).upper()
    try:
        resp = send(f"{base.rstrip('/')}/api/negotiate", json=body,
                    headers={"X-API-Key": key}, timeout=timeout)
    except httpx.HTTPError as exc:
        log.warning("return_saver negotiate failed: %s", exc.__class__.__name__)
        return PluginReply.fallback("transport_error")

    if resp.status_code not in (200, 422):
        log.warning("return_saver negotiate HTTP %s", resp.status_code)
        return PluginReply.fallback(f"http_{resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        log.warning("return_saver negotiate returned a non-JSON body")
        return PluginReply.fallback("bad_response")

    if data.get("status") == "passthrough":
        return PluginReply.fallback("passthrough")

    offer = data.get("offer")
    if offer is not None and "offer_token" not in offer and data.get("offer_token"):
        offer = {**offer, "offer_token": data["offer_token"]}

    meta = {k: data[k] for k in ("cost_usd", "stage", "model_calls",
                                 "guardrail", "experience_warning")
            if k in data}
    return PluginReply(
        handled=True,
        answer=data.get("reply", ""),
        ext_session_id=data.get("session_id"),
        closed=(resp.status_code == 422 or data.get("stage") == "closed"),
        offer=offer,
        escape_hatch=data.get("escape_hatch"),
        next_action=data.get("next_action"),
        status=data.get("status"),
        meta=meta,
    )


def accept(body: dict, *, base: str, key: str, timeout: float,
           post: Optional[Callable] = None) -> tuple[int, dict]:
    token = (body or {}).get("offer_token")
    idem = (body or {}).get("idempotency_key")
    if not token or not idem:
        return 400, {"detail": "offer_token and idempotency_key are required"}
    send = post or _default_post
    try:
        resp = send(f"{base.rstrip('/')}/api/accept",
                    json={"offer_token": token, "idempotency_key": idem},
                    headers={"X-API-Key": key}, timeout=timeout)
    except httpx.HTTPError as exc:
        log.warning("return_saver accept failed: %s", exc.__class__.__name__)
        return 502, {"detail": "return saver unreachable"}
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return 502, {"detail": "return saver returned a non-JSON body"}


def _is_escape(question: str) -> bool:
    return (question or "").strip() in ESCAPE_PHRASES


def _default_post(url: str, *, json: dict, headers: dict, timeout: float):
    # Service-to-service plugin calls must not inherit a desktop HTTP proxy.
    # A proxy can turn a healthy localhost Return Saver into an opaque 503.
    with httpx.Client(trust_env=False) as client:
        return client.post(url, json=json, headers=headers, timeout=timeout)
