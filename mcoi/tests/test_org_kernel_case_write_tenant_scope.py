"""Cross-tenant scoping for organization-kernel case *mutation* endpoints.

Companion to test_org_kernel_case_tenant_scope.py (which covered the case reads
and the launch-gateway handlers). These seven write endpoints mutated a case by
id with no tenant check, so an authenticated caller for tenant A could create
plans, admit evidence, record approvals, evaluate plan-step gates, bind worker
receipts, CLOSE, or bind learning admissions on tenant B's governance case.

Each now calls _enforce_case_tenant(request, kernel, case_id) right after
resolving the kernel, before any mutation -- so the cross-tenant request is
rejected (403) before the write. enforce_tenant_scope is a no-op for operators
(wildcard scope) and unauthenticated dev requests.
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
    scopes = frozenset({"*"}) if operator else frozenset({"musia.write"})
    return _Req({"authenticated_tenant_id": tenant_id, "jwt_scopes": scopes})


class _Case:
    org_id = "org-x"


class _Kernel:
    """A case in org-x owned by tenant-b."""

    def get_case(self, case_id):
        return _Case()

    def organization_tenant(self, org_id):
        return "tenant-b"


class _Body:
    """Placeholder request body -- the tenant check fires before it is read."""


@pytest.fixture
def cross_tenant_kernel(monkeypatch):
    monkeypatch.setattr(ok, "_kernel", lambda: _Kernel())


def test_create_case_plan_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.create_case_plan("case-1", _Body(), _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_admit_case_evidence_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.admit_case_evidence("case-1", _Body(), _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_record_case_approval_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.record_case_approval("case-1", _Body(), _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_evaluate_case_plan_step_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.evaluate_case_plan_step("case-1", "step-1", _Body(), _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_bind_plan_step_worker_receipt_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.bind_plan_step_worker_receipt("case-1", "step-1", _Body(), _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_close_case_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.close_case("case-1", _Body(), _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_bind_case_learning_admission_rejects_cross_tenant(cross_tenant_kernel):
    with pytest.raises(HTTPException) as exc:
        ok.bind_case_learning_admission("case-1", _Body(), _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_close_case_operator_passes_tenant_gate(cross_tenant_kernel):
    # Operator (wildcard scope) clears the tenant gate; the mutation then fails
    # on the placeholder body, which is NOT a 403 -- proving the gate was passed.
    with pytest.raises(Exception) as exc:
        ok.close_case("case-1", _Body(), _authed("tenant-a", operator=True))
    assert not (isinstance(exc.value, HTTPException) and exc.value.status_code == 403)
