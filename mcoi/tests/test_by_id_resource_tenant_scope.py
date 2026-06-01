"""Cross-tenant scoping for by-id resource reads (linter-blind class).

GET handlers that fetch a record by a resource id (case_id, schedule_id,
pilot_id, audit entry_index, ticket_id) and return it have no `tenant_id`
parameter, so the tenant-scope linter cannot see them. Each fetched record is
tenant-owned, so without a post-fetch check an authenticated caller for tenant A
could read tenant B's finance proof / schedule / pilot provision / audit entry
by guessing or enumerating the id.

Fix: after the record is fetched, enforce_tenant_scope(request, record.tenant_id)
rejects a non-operator whose authenticated tenant differs (403); operators and
unauthenticated dev requests are unaffected. god-mode ticket reads are an
operator surface, gated by require_admin (consistent with god-mode list/issue).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers import explain, finance_approval, god_mode, pilot, temporal_scheduler
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
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


class _Owned:
    """Minimal record owned by tenant-b."""
    tenant_id = "tenant-b"

    def to_dict(self):
        return {"tenant_id": self.tenant_id}


# -- finance approval packet proof -----------------------------------------

class _FinanceStore:
    def get_case(self, case_id):
        return _Owned()


def test_finance_proof_rejects_cross_tenant(monkeypatch):
    monkeypatch.setattr(finance_approval, "_store", lambda: _FinanceStore())
    with pytest.raises(HTTPException) as exc:
        finance_approval.get_finance_approval_packet_proof("case-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


# -- temporal schedule by id -----------------------------------------------

class _TemporalStore:
    def get_action(self, schedule_id):
        return _Owned()

    def list_receipts(self, *, schedule_id):
        return ()


def test_temporal_schedule_rejects_cross_tenant(monkeypatch):
    monkeypatch.setattr(temporal_scheduler.deps, "temporal_scheduler_store", _TemporalStore())
    with pytest.raises(HTTPException) as exc:
        temporal_scheduler.get_temporal_schedule("sched-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


# -- pilot provision by id -------------------------------------------------

class _Registry:
    def get(self, pilot_id):
        return _Owned()


def test_pilot_provision_rejects_cross_tenant(monkeypatch):
    monkeypatch.setattr(pilot, "_provision_registry", _Registry())
    with pytest.raises(HTTPException) as exc:
        pilot.get_pilot_provision("pilot-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


# -- audit entry by index (queries the GLOBAL trail, then indexes) ---------

class _AuditTrail:
    def query(self, limit):
        return [_Owned()]


def test_explain_audit_entry_rejects_cross_tenant(monkeypatch):
    monkeypatch.setattr(explain.deps, "audit_trail", _AuditTrail())
    with pytest.raises(HTTPException) as exc:
        explain.explain_audit_entry(0, _authed("tenant-a"))
    assert exc.value.status_code == 403


# -- god-mode ticket by id (operator surface, require_admin) ---------------

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


def test_get_ticket_requires_admin_scope(god_mode_client):
    client, manager = god_mode_client
    read_raw, _ = manager.create_key(tenant_id="tenant-a", scopes=frozenset({"musia.read"}))
    denied = client.get(
        "/api/v1/god-mode/tickets/ticket-1",
        headers={"Authorization": f"Bearer {read_raw}"},
    )
    assert denied.status_code == 403
    assert "musia.admin" in denied.text


def test_get_ticket_allows_admin_scope(god_mode_client):
    client, manager = god_mode_client
    admin_raw, _ = manager.create_key(tenant_id="tenant-a", scopes=frozenset({"musia.admin"}))
    allowed = client.get(
        "/api/v1/god-mode/tickets/ticket-1",
        headers={"Authorization": f"Bearer {admin_raw}"},
    )
    # Passes the admin gate; a missing ticket then yields 404 -- not a 403 denial.
    assert allowed.status_code != 403
