"""LLM cost analytics endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Request

from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope
from mcoi_runtime.app.routers.llm._common import deps

router = APIRouter()


@router.get("/api/v1/costs")
def cost_summary():
    """Overall cost analytics summary."""
    return deps.cost_analytics.summary()


@router.get("/api/v1/costs/top-spenders")
def top_spenders(limit: int = 10):
    """Top spending tenants."""
    return {
        "spenders": [
            {"tenant_id": b.tenant_id, "total_cost": b.total_cost, "calls": b.call_count}
            for b in deps.cost_analytics.top_spenders(limit=limit)
        ],
    }


@router.get("/api/v1/costs/by-model")
def costs_by_model():
    """Cost breakdown by LLM model."""
    return {"models": deps.cost_analytics.model_usage()}


@router.get("/api/v1/costs/{tenant_id}")
def tenant_costs(tenant_id: str, request: Request):
    """Cost breakdown for a specific tenant."""
    enforce_tenant_scope(request, tenant_id)
    breakdown = deps.cost_analytics.tenant_breakdown(tenant_id)
    return {
        "tenant_id": breakdown.tenant_id,
        "total_cost": breakdown.total_cost,
        "total_tokens": breakdown.total_tokens,
        "call_count": breakdown.call_count,
        "avg_cost_per_call": breakdown.avg_cost_per_call,
        "by_model": breakdown.by_model,
        "most_expensive_model": breakdown.most_expensive_model,
    }


@router.get("/api/v1/costs/{tenant_id}/projection")
def cost_projection(tenant_id: str, request: Request, budget: float = 0.0, days_elapsed: float = 1.0):
    """Cost projection for a tenant."""
    enforce_tenant_scope(request, tenant_id)
    proj = deps.cost_analytics.project(tenant_id, budget=budget, days_elapsed=days_elapsed)
    return {
        "tenant_id": proj.tenant_id,
        "current_daily_rate": proj.current_daily_rate,
        "projected_monthly": proj.projected_monthly,
        "budget_remaining": proj.budget_remaining,
        "days_until_exhaustion": proj.days_until_exhaustion,
    }
