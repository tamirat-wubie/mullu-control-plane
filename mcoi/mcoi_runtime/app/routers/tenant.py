"""Tenant-related endpoints extracted from server.py.

Provides budget management, ledger queries, usage reports, analytics,
isolation verification, quota enforcement, and partition management.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mcoi_runtime.core.tenant_budget import TenantBudgetPolicy, TenantBudgetReport
from mcoi_runtime.core.tenant_gating import TenantGatingError, TenantStatus
from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


# ── Helpers & request models ─────────────────────────────────────────────


def _tenant_error_detail(error: str, error_code: str) -> dict[str, Any]:
    return {"error": error, "error_code": error_code, "governed": True}


def _tenant_error_response(exc: TenantGatingError) -> tuple[int, dict[str, Any]]:
    return exc.http_status_code, _tenant_error_detail(exc.public_error, exc.error_code)


class TenantBudgetRequest(BaseModel):
    tenant_id: str
    max_cost: float = 10.0
    max_calls: int = 1000


class TenantRegisterRequest(BaseModel):
    tenant_id: str
    status: str = "onboarding"
    reason: str = ""


class TenantStatusUpdateRequest(BaseModel):
    status: str
    reason: str = ""


def _budget_report(r: TenantBudgetReport) -> dict[str, Any]:
    return {
        "tenant_id": r.tenant_id, "budget_id": r.budget_id, "max_cost": r.max_cost,
        "spent": r.spent, "remaining": r.remaining, "calls_made": r.calls_made,
        "max_calls": r.max_calls, "exhausted": r.exhausted, "enabled": r.enabled,
        "utilization_pct": r.utilization_pct,
    }


# ── Budget CRUD ──────────────────────────────────────────────────────────


@router.post("/api/v1/tenant/budget")
def create_tenant_budget(req: TenantBudgetRequest):
    """Create or update a tenant's budget policy."""
    deps.tenant_budget_mgr.set_policy(TenantBudgetPolicy(
        tenant_id=req.tenant_id, max_cost=req.max_cost, max_calls=req.max_calls,
    ))
    deps.tenant_budget_mgr.ensure_budget(req.tenant_id)
    deps.audit_trail.record(
        action="tenant.budget.create", actor_id="system",
        tenant_id=req.tenant_id, target=req.tenant_id, outcome="success",
    )
    deps.metrics.inc("requests_governed")
    return _budget_report(deps.tenant_budget_mgr.report(req.tenant_id))


@router.get("/api/v1/tenant/{tenant_id}/budget")
def get_tenant_budget(tenant_id: str):
    """Get a tenant's budget report."""
    deps.metrics.inc("requests_governed")
    return _budget_report(deps.tenant_budget_mgr.report(tenant_id))


# ── Ledger ───────────────────────────────────────────────────────────────


@router.get("/api/v1/tenant/{tenant_id}/ledger")
def get_tenant_ledger(tenant_id: str, entry_type: str | None = None, limit: int = 50):
    """Get a tenant's scoped ledger entries."""
    deps.metrics.inc("requests_governed")
    entries = deps.tenant_ledger.query(tenant_id, entry_type=entry_type, limit=limit)
    return {
        "entries": [{"entry_id": e.entry_id, "type": e.entry_type, "actor": e.actor_id,
                      "content": e.content, "at": e.recorded_at} for e in entries],
        "count": len(entries),
        "tenant_id": tenant_id,
    }


@router.get("/api/v1/tenant/{tenant_id}/summary")
def get_tenant_summary(tenant_id: str):
    """Get a tenant's ledger summary."""
    deps.metrics.inc("requests_governed")
    summary = deps.tenant_ledger.summary(tenant_id)
    return {
        "tenant_id": summary.tenant_id,
        "total_entries": summary.total_entries,
        "entry_types": summary.entry_types,
        "total_cost": summary.total_cost,
    }


# ── Tenant listing ───────────────────────────────────────────────────────


@router.get("/api/v1/tenants")
def list_tenants():
    """List all tenants with budgets and ledger activity."""
    deps.metrics.inc("requests_governed")
    return {
        "tenants": deps.tenant_budget_mgr.all_reports(),
        "ledger_tenants": deps.tenant_ledger.all_tenant_ids(),
        "total_spent": deps.tenant_budget_mgr.total_spent(),
    }


# ── Usage reports ────────────────────────────────────────────────────────


@router.get("/api/v1/usage/{tenant_id}")
def tenant_usage(tenant_id: str):
    """Per-tenant usage report."""
    report = deps.usage_reporter.generate(tenant_id)
    return {
        "tenant_id": report.tenant_id,
        "llm_calls": report.llm_calls,
        "total_cost": report.total_cost,
        "generated_at": report.generated_at,
    }


# ── Analytics ────────────────────────────────────────────────────────────


@router.get("/api/v1/analytics/{tenant_id}")
def tenant_analytics_endpoint(tenant_id: str):
    """Per-tenant analytics dashboard."""
    analytics = deps.tenant_analytics.compute(tenant_id)
    return {
        "tenant_id": analytics.tenant_id,
        "llm_calls": analytics.llm_calls,
        "total_cost": analytics.total_cost,
        "conversations": analytics.conversations,
        "workflows": analytics.workflows,
        "generated_at": analytics.generated_at,
    }


# ── Isolation verification ───────────────────────────────────────────────


@router.post("/api/v1/isolation/verify")
def verify_isolation(tenant_a: str = "probe-a", tenant_b: str = "probe-b"):
    """Verify tenant isolation between two tenants."""
    deps.metrics.inc("requests_governed")
    report = deps.isolation_verifier.verify(tenant_a, tenant_b)
    return {
        "all_isolated": report.all_isolated,
        "probes_run": report.probes_run,
        "probes_passed": report.probes_passed,
        "probes": [
            {"name": p.probe_name, "isolated": p.isolated, "detail": p.detail}
            for p in report.probes
        ],
        "verified_at": report.verified_at,
    }


@router.get("/api/v1/isolation/summary")
def isolation_summary():
    """Isolation verification summary."""
    return deps.isolation_verifier.summary()


# ── Tenant isolation audits ──────────────────────────────────────────────


@router.get("/api/v1/tenant-isolation")
def get_tenant_isolation_summary():
    """Return tenant isolation audit summary."""
    deps.metrics.inc("requests_governed")
    return {"tenant_isolation": deps.tenant_isolation.summary(), "governed": True}


@router.get("/api/v1/tenant-isolation/audits")
def get_recent_isolation_audits(count: int = 10):
    """Return recent tenant isolation audit results."""
    deps.metrics.inc("requests_governed")
    audits = deps.tenant_isolation.recent_audits(count)
    return {
        "audits": [a.to_dict() for a in audits],
        "count": len(audits),
        "governed": True,
    }


# ── Quota enforcement ────────────────────────────────────────────────────


@router.get("/api/v1/quotas/summary")
def get_quotas_summary():
    """Return tenant quota enforcement summary."""
    deps.metrics.inc("requests_governed")
    return {"quotas": deps.tenant_quota.summary(), "governed": True}


@router.get("/api/v1/quotas/{tenant_id}")
def get_tenant_quota_usage(tenant_id: str):
    """Return quota usage for a specific tenant."""
    deps.metrics.inc("requests_governed")
    return {"tenant_id": tenant_id, "usage": deps.tenant_quota.get_usage(tenant_id), "governed": True}


# ── Tenant partitions ────────────────────────────────────────────────────


@router.get("/api/v1/partitions")
def get_partitions():
    """Return tenant data partition summary."""
    deps.metrics.inc("requests_governed")
    return {
        "partitions": deps.tenant_partitions.summary(),
        "tenants": [p.to_dict() for p in deps.tenant_partitions.list_partitions()],
        "governed": True,
    }


# ── Tenant gating / lifecycle ──────────────────────────────────────────


def _require_gating():
    """Get tenant gating registry or raise 503."""
    gating = deps.get("tenant_gating")
    if gating is None:
        raise HTTPException(
            503,
            detail=_tenant_error_detail("tenant gating not initialized", "tenant_gating_unavailable"),
        )
    return gating


@router.post("/api/v1/tenant/register")
def register_tenant(req: TenantRegisterRequest):
    """Register a new tenant with initial lifecycle status."""
    gating = _require_gating()
    try:
        status = TenantStatus(req.status)
    except ValueError:
        raise HTTPException(422, detail=_tenant_error_detail("invalid status", "invalid_status")) from None
    try:
        gate = gating.register(req.tenant_id, status=status, reason=req.reason)
    except TenantGatingError as exc:
        status_code, detail = _tenant_error_response(exc)
        raise HTTPException(status_code, detail=detail) from exc
    except ValueError as exc:
        status_code, detail = 400, _tenant_error_detail("tenant lifecycle request failed", "tenant_lifecycle_error")
        raise HTTPException(status_code, detail=detail) from exc
    deps.audit_trail.record(
        action="tenant.register", actor_id="api",
        tenant_id=req.tenant_id, target=req.tenant_id,
        outcome="success", detail={"status": gate.status.value},
    )
    return {
        "tenant_id": gate.tenant_id,
        "status": gate.status.value,
        "reason": gate.reason,
        "gated_at": gate.gated_at,
        "governed": True,
    }


@router.patch("/api/v1/tenant/{tenant_id}/status")
def update_tenant_status(tenant_id: str, req: TenantStatusUpdateRequest):
    """Update tenant lifecycle status (suspend, terminate, reactivate)."""
    gating = _require_gating()
    try:
        new_status = TenantStatus(req.status)
    except ValueError:
        raise HTTPException(422, detail=_tenant_error_detail("invalid status", "invalid_status")) from None
    try:
        gate = gating.update_status(tenant_id, new_status, reason=req.reason)
    except TenantGatingError as exc:
        status_code, detail = _tenant_error_response(exc)
        raise HTTPException(status_code, detail=detail) from exc
    except ValueError as exc:
        status_code, detail = 400, _tenant_error_detail("tenant lifecycle request failed", "tenant_lifecycle_error")
        raise HTTPException(status_code, detail=detail) from exc
    deps.audit_trail.record(
        action="tenant.status.update", actor_id="api",
        tenant_id=tenant_id, target=tenant_id,
        outcome="success", detail={"new_status": gate.status.value, "reason": gate.reason},
    )
    return {
        "tenant_id": gate.tenant_id,
        "status": gate.status.value,
        "reason": gate.reason,
        "gated_at": gate.gated_at,
        "governed": True,
    }


@router.get("/api/v1/tenant/{tenant_id}/gate")
def get_tenant_gate(tenant_id: str):
    """Get tenant lifecycle gating status."""
    gating = _require_gating()
    gate = gating.get_status(tenant_id)
    if gate is None:
        return {"tenant_id": tenant_id, "status": "unknown", "governed": True}
    return {
        "tenant_id": gate.tenant_id,
        "status": gate.status.value,
        "reason": gate.reason,
        "gated_at": gate.gated_at,
        "governed": True,
    }


@router.get("/api/v1/tenant/gates")
def list_tenant_gates():
    """List all tenant lifecycle gates."""
    gating = _require_gating()
    return {
        "gates": [
            {"tenant_id": g.tenant_id, "status": g.status.value, "reason": g.reason}
            for g in gating.all_gates()
        ],
        "summary": gating.summary(),
        "governed": True,
    }
