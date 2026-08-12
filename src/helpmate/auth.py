"""Caller identity — the principal every request is authorized against.

Without this layer "multi-tenant isolation" is self-declared: a caller could put
any `tenant_id` in the request body and read another tenant's documents, and the
order tools would happily look up any `order_id` at all.

A principal carries two things:
  tenant_id   — which document corpus the caller may retrieve from
  customer_id — whose orders/shipments the caller may look up (None = no order
                access at all, so an unauthenticated caller can never reach
                business data)

Configuration (`API_KEYS`, JSON in `.env`) maps an API key to `"tenant"` or
`"tenant:customer"`:

    API_KEYS={"sk-dji-alice": "dji:Alice", "sk-dji-ops": "dji"}

When `API_KEYS` is empty the service runs in **dev mode**: every request is
treated as `default_tenant` / `default_customer` so `clone && run` still works.
Dev mode is a local convenience, not an auth bypass — the ownership checks
downstream stay on in both modes.
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException

from helpmate.config import get_settings


@dataclass(frozen=True)
class Principal:
    """Authenticated caller. `customer_id=None` means no order-data access."""
    tenant_id: str
    customer_id: Optional[str] = None
    dev_mode: bool = False


def parse_grant(grant: str) -> tuple[str, Optional[str]]:
    """Split a configured grant string into (tenant_id, customer_id)."""
    tenant, _, customer = grant.partition(":")
    return tenant.strip(), (customer.strip() or None)


def principal_from_key(api_key: Optional[str]) -> Optional[Principal]:
    """Resolve an API key to a Principal. None when the key is unknown.

    Dev mode (no keys configured) returns the default identity so the demo
    corpus and seeded orders remain reachable without setup.
    """
    s = get_settings()
    if not s.api_keys:
        return Principal(tenant_id=s.default_tenant,
                         customer_id=s.default_customer or None,
                         dev_mode=True)
    if not api_key:
        return None
    grant = s.api_keys.get(api_key)
    if grant is None:
        return None
    tenant, customer = parse_grant(grant)
    return Principal(tenant_id=tenant or s.default_tenant, customer_id=customer)


def require_principal(x_api_key: Optional[str] = Header(default=None)) -> Principal:
    """FastAPI dependency: resolve `X-API-Key` into a Principal or 401."""
    p = principal_from_key(x_api_key)
    if p is None:
        raise HTTPException(status_code=401, detail="missing or invalid API key")
    return p
