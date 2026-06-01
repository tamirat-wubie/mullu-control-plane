"""Cross-tenant IDOR regression for the governed swarm run endpoints.

GET /api/v1/swarm/runs and /runs/{run_id} returned invoice/financial audit
records with no tenant scoping: list_runs returned ALL tenants' runs and get_run
returned any run by id. The runtime now accepts a scope_tenant filter, which the
FastAPI router derives from the authenticated request tenant (operator and
unauthenticated/dev requests stay unconfined).
"""

from __future__ import annotations

from decimal import Decimal

from mcoi_runtime.swarm import (
    InvoiceSwarmRuntime,
    SwarmAuditStore,
    invoice_result_to_audit_record,
)
from mcoi_runtime.swarm.fastapi_router import _request_scope_tenant
from mcoi_runtime.swarm.invoice_workflow import InvoiceSwarmRequest, run_invoice_swarm


def _request(tenant_id: str) -> InvoiceSwarmRequest:
    return InvoiceSwarmRequest(
        goal_id="g",
        tenant_id=tenant_id,
        invoice_ref="r",
        invoice_amount_usd=Decimal("320.00"),
        vendor_verified=True,
        duplicate_found=False,
        budget_available=True,
        human_approved=True,
        policy_requires_approval=True,
    )


def _runtime_with_two_tenants(tmp_path) -> InvoiceSwarmRuntime:
    store = SwarmAuditStore(tmp_path / "runs.jsonl")
    store.append(invoice_result_to_audit_record(
        run_id="run-a", tenant_id="tenant-a",
        result=run_invoice_swarm(_request("tenant-a")), created_at="2026-05-05T12:00:00Z",
    ))
    store.append(invoice_result_to_audit_record(
        run_id="run-b", tenant_id="tenant-b",
        result=run_invoice_swarm(_request("tenant-b")), created_at="2026-05-05T12:00:00Z",
    ))
    return InvoiceSwarmRuntime(store)


def test_list_runs_scoped_to_tenant(tmp_path):
    runtime = _runtime_with_two_tenants(tmp_path)
    scoped = runtime.list_runs(scope_tenant="tenant-a").to_dict()
    run_ids = {r["run_id"] for r in scoped["payload"]["records"]}
    assert run_ids == {"run-a"}
    # No scope (operator / CLI / worker) still sees all.
    assert runtime.list_runs().to_dict()["payload"]["count"] == 2


def test_get_run_cross_tenant_is_not_found(tmp_path):
    runtime = _runtime_with_two_tenants(tmp_path)
    cross = runtime.get_run("run-b", scope_tenant="tenant-a").to_dict()
    assert cross["ok"] is False
    assert cross["status"] == "not_found"
    # The caller's own run is returned.
    assert runtime.get_run("run-a", scope_tenant="tenant-a").to_dict()["ok"] is True


class _State:
    def __init__(self, ctx):
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx):
        self.state = _State(ctx)


def test_request_scope_tenant_confines_authenticated_caller():
    assert _request_scope_tenant(_Req({"authenticated_tenant_id": "tenant-a"})) == "tenant-a"


def test_request_scope_tenant_operator_and_dev_are_unconfined():
    operator = _Req({"authenticated_tenant_id": "tenant-a", "jwt_scopes": frozenset({"*"})})
    assert _request_scope_tenant(operator) is None
    assert _request_scope_tenant(_Req({})) is None
