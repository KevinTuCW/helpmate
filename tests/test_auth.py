"""Identity resolution — the layer that makes 'multi-tenant' more than a claim."""
import pytest
from fastapi import HTTPException

from helpmate import auth
from helpmate.config import Settings


def _with_settings(monkeypatch, **kwargs):
    s = Settings(_env_file=None, **kwargs)
    monkeypatch.setattr(auth, "get_settings", lambda: s)
    return s


def test_dev_mode_grants_the_default_identity(monkeypatch):
    _with_settings(monkeypatch, api_keys={})
    p = auth.principal_from_key(None)
    assert p.tenant_id == "public"
    assert p.customer_id == "Alice"
    assert p.dev_mode is True


def test_configured_keys_reject_missing_or_unknown_keys(monkeypatch):
    _with_settings(monkeypatch, api_keys={"sk-a": "dji:Alice"})
    assert auth.principal_from_key(None) is None
    assert auth.principal_from_key("sk-nope") is None


def test_grant_maps_key_to_tenant_and_customer(monkeypatch):
    _with_settings(monkeypatch, api_keys={"sk-a": "dji:Alice", "sk-ops": "dji"})
    alice = auth.principal_from_key("sk-a")
    assert (alice.tenant_id, alice.customer_id) == ("dji", "Alice")

    # An ops key scoped to the tenant only gets no order access at all.
    ops = auth.principal_from_key("sk-ops")
    assert (ops.tenant_id, ops.customer_id) == ("dji", None)


def test_require_principal_raises_401_without_a_valid_key(monkeypatch):
    _with_settings(monkeypatch, api_keys={"sk-a": "dji:Alice"})
    with pytest.raises(HTTPException) as exc:
        auth.require_principal(x_api_key=None)
    assert exc.value.status_code == 401


def test_parse_grant_handles_tenant_only_and_whitespace():
    assert auth.parse_grant("dji:Alice") == ("dji", "Alice")
    assert auth.parse_grant(" dji ") == ("dji", None)
    assert auth.parse_grant("dji:") == ("dji", None)
