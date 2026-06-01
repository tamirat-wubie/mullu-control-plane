"""Cross-tenant scoping for the remaining scalar-`tenant_id` query handlers.

Follow-up to test_query_param_tenant_scope.py: the linter's scalar-`tenant_id`
check surfaced eight further handlers that read tenant-partitioned state by a
caller-supplied query parameter. Seven are tenant-self listings now forced to
the authenticated tenant via scoped_listing_tenant; one (god-mode ticket
listing) is an operator surface gated by require_admin, consistent with
god-mode issue_ticket.

These tests prove the scoping is wired: a non-operator naming a different tenant
is rejected (403), the god-mode listing requires the admin scope in auth mode,
and a non-operator's empty claim is forced to its own tenant (not "all tenants").
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers import agent, console, pilot, rbac, temporal_scheduler
from mcoi_runtime.app.routers import god_mode
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.app.routers.ops import feature_flags
from mcoi_runtime.governance.auth.api_key import APIKeyManager


class _State:
    def __init__(self, ctx: dict) -> None:
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx: dict) -> None:
        self.state = _State(ctx)


def _authed(tenant_id: str, *, operator: bool = False) -> _Req:
    scopes = frozenset({"*"}) if operator else frozenset({"musia.read"})
    return _Req({"authenticated_tenant_id": tenant_id, "jwt_scopes": scopes})


# --------------------------------------------------------------------------
# Tenant-self listings: a non-operator naming another tenant is rejected.
# The scope helper raises before the backing store is queried.
# --------------------------------------------------------------------------

def test_list_webhooks_rejects_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        agent.list_webhooks(_authed("tenant-a"), tenant_id="tenant-b")
    assert exc.value.status_code == 403


def test_console_runs_rejects_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        console.console_runs(_authed("tenant-a"), tenant_id="tenant-b")
    assert exc.value.status_code == 403


def test_console_audit_rejects_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        console.console_audit(_authed("tenant-a"), tenant_id="tenant-b")
    assert exc.value.status_code == 403


def test_check_flag_rejects_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        feature_flags.check_flag("flag-x", _authed("tenant-a"), tenant_id="tenant-b")
    assert exc.value.status_code == 403


def test_list_pilot_provisions_rejects_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        pilot.list_pilot_provisions(_authed("tenant-a"), tenant_id="tenant-b")
    assert exc.value.status_code == 403


def test_list_temporal_schedules_rejects_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        temporal_scheduler.list_temporal_schedules(_authed("tenant-a"), tenant_id="tenant-b")
    assert exc.value.status_code == 403


def test_list_identities_rejects_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        rbac.list_identities(_authed("tenant-a"), tenant_id="tenant-b")
    assert exc.value.status_code == 403


# --------------------------------------------------------------------------
# Empty claim is forced to the caller's own tenant (rbac identities), so the
# `tenant_id=""` "return everything" default cannot leak other tenants.
# --------------------------------------------------------------------------

class _CapturingAccessRuntime:
    def __init__(self) -> None:
        self.scoped_calls: list[str] = []
        self.all_called = 0

    def identities_for_tenant(self, tenant_id):
        self.scoped_calls.append(tenant_id)
        return ()

    def all_identities(self):
        self.all_called += 1
        return ()


def test_list_identities_forces_own_tenant_when_unspecified(monkeypatch):
    fake = _CapturingAccessRuntime()
    monkeypatch.setattr(rbac.deps, "access_runtime", fake)
    rbac.list_identities(_authed("tenant-a"), tenant_id="")
    assert fake.scoped_calls == ["tenant-a"]  # scoped to own tenant
    assert fake.all_called == 0  # never widened to all identities


# --------------------------------------------------------------------------
# god-mode ticket listing is operator-only (require_admin), in auth mode.
# --------------------------------------------------------------------------

@pytest.fixture
def god_mode_client():
    manager = APIKeyManager()
    configure_musia_auth(manager)
    app = FastAPI()
    app.include_router(god_mode.router)
    try:
        yield TestClient(app), manager
    finally:
        configure_musia_auth(None)


def test_list_tickets_requires_admin_scope(god_mode_client):
    client, manager = god_mode_client
    read_raw, _ = manager.create_key(tenant_id="tenant-a", scopes=frozenset({"musia.read"}))
    denied = client.get(
        "/api/v1/god-mode/tickets",
        headers={"Authorization": f"Bearer {read_raw}"},
    )
    assert denied.status_code == 403
    assert "musia.admin" in denied.text


def test_list_tickets_allows_admin_scope(god_mode_client):
    client, manager = god_mode_client
    admin_raw, _ = manager.create_key(tenant_id="tenant-a", scopes=frozenset({"musia.admin"}))
    allowed = client.get(
        "/api/v1/god-mode/tickets",
        headers={"Authorization": f"Bearer {admin_raw}"},
    )
    assert allowed.status_code != 403
