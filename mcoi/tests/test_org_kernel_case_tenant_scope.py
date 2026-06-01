"""Cross-tenant scoping for organization-kernel case endpoints.

Organization cases carry an org_id, not a tenant_id; the owning tenant is resolved
through the organization (case.org_id -> OrganizationProfile.tenant_id). Case read
and launch-gateway-pilot handlers previously returned/mutated any case by id with
no tenant check, so an authenticated caller for tenant A could read tenant B's
case bundle, proof timeline, events, gate preview, or readiness -- or drive the
deployment-witness / readiness-closure mutations against B's case.

_enforce_case_tenant resolves the case's org -> tenant and rejects a non-operator
whose authenticated tenant differs (403). enforce_tenant_scope is a no-op for
operators (wildcard scope) and unauthenticated dev requests.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers import organization_kernel as ok


class _State:
    def __init__(self, ctx: dict) -> None:
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx: dict) -> None:
        self.state = _State(ctx)


def _authed(tenant_id: str, *, operator: bool = False) -> _Req:
    scopes = frozenset({"*"}) if operator else frozenset({"musia.read"})
    return _Req({"authenticated_tenant_id": tenant_id, "jwt_scopes": scopes})


def _unauth() -> _Req:
    return _Req({})


class _Case:
    org_id = "org-x"


class _Kernel:
    """Minimal kernel: a case in org-x owned by the given tenant."""

    def __init__(self, tenant):
        self._tenant = tenant

    def get_case(self, case_id):
        return _Case()

    def organization_tenant(self, org_id):
        return self._tenant


# -- the resolver/enforcer itself ------------------------------------------

def test_enforce_case_tenant_rejects_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        ok._enforce_case_tenant(_authed("tenant-a"), _Kernel("tenant-b"), "case-1")
    assert exc.value.status_code == 403


def test_enforce_case_tenant_allows_own_tenant():
    ok._enforce_case_tenant(_authed("tenant-a"), _Kernel("tenant-a"), "case-1")


def test_enforce_case_tenant_operator_passthrough():
    ok._enforce_case_tenant(_authed("tenant-a", operator=True), _Kernel("tenant-b"), "case-1")


def test_enforce_case_tenant_unauthenticated_passthrough():
    ok._enforce_case_tenant(_unauth(), _Kernel("tenant-b"), "case-1")


def test_enforce_case_tenant_unknown_org_is_noop():
    # organization_tenant returns None -> nothing to enforce, no false 403.
    ok._enforce_case_tenant(_authed("tenant-a"), _Kernel(None), "case-1")


# -- handlers (reads + a write) reject cross-tenant ------------------------

@pytest.fixture
def cross_tenant_kernel(monkeypatch):
    monkeypatch.setattr(ok, "_kernel", lambda: _Kernel("tenant-b"))


def test_get_case_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.get_case("case-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_get_case_proof_timeline_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.get_case_proof_timeline("case-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_get_case_audit_explorer_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.get_case_audit_explorer("case-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_get_case_audit_explorer_view_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.get_case_audit_explorer_view("case-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_list_case_events_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.list_case_events("case-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_gate_preview_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.get_launch_gateway_pilot_gate_preview("case-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_deployment_witness_write_rejects_cross_tenant(cross_tenant_kernel):
    # The tenant check fires before any evidence-collection logic, so a bare
    # placeholder request object never gets used.
    class _Body:
        pass

    with pytest.raises(HTTPException) as exc:
        ok.collect_launch_gateway_pilot_deployment_witness("case-1", _Body(), _authed("tenant-a"))
    assert exc.value.status_code == 403
