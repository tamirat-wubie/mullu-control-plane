"""Operator Console — unified operational views for operations teams.

Aggregates runtime state into structured dashboard views that any
frontend can consume. Five views cover the core operational needs:

- Home: active/blocked/failed runs, provider health, budget burn
- Runs: current state, ledger links, verification, restore eligibility
- Audit: searchable event history by tenant/provider/policy/actor
- Checkpoints: saved coordination state, resumable/expired/blocked
- Providers: Anthropic/OpenAI/Gemini/Ollama status, latency, cost
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


# ═══ Home Dashboard ═══


@router.get("/api/v1/console/home")
def console_home():
    """Operator home dashboard — key vitals at a glance."""
    deps.metrics.inc("requests_governed")

    # Collect vitals from subsystems
    audit_summary = deps.audit_trail.summary()
    scheduler_summary = deps.scheduler.summary()
    llm_summary = deps.llm_bridge.budget_summary()

    # Count outcomes from recent audit entries
    recent = deps.audit_trail.query(limit=200)
    active = sum(1 for e in recent if e.outcome == "success")
    blocked = sum(1 for e in recent if e.outcome in ("denied", "blocked"))
    failed = sum(1 for e in recent if e.outcome in ("error", "failed"))

    return {
        "active_runs": active,
        "blocked_runs": blocked,
        "failed_runs": failed,
        "total_audit_entries": audit_summary.get("entry_count", 0),
        "chain_intact": deps.audit_trail.verify_chain(),
        "llm_invocations": deps.llm_bridge.invocation_count,
        "llm_total_cost": deps.llm_bridge.total_cost,
        "active_tenants": deps.tenant_budget_mgr.tenant_count(),
        "total_spent": deps.tenant_budget_mgr.total_spent(),
        "scheduler": scheduler_summary,
        "circuit_breaker": deps.llm_circuit.state.value,
        "event_count": deps.event_bus.event_count,
        "health_score": deps.health_agg.compute().overall_score,
        "governed": True,
    }


# ═══ Runs View ═══


@router.get("/api/v1/console/runs")
def console_runs(
    tenant_id: str | None = None,
    outcome: str | None = None,
    limit: int = 50,
):
    """Operator runs view — recent governed actions with status."""
    deps.metrics.inc("requests_governed")
    entries = deps.audit_trail.query(
        tenant_id=tenant_id,
        outcome=outcome,
        limit=limit,
    )
    return {
        "runs": [
            {
                "entry_id": e.entry_id,
                "action": e.action,
                "actor_id": e.actor_id,
                "tenant_id": e.tenant_id,
                "target": e.target,
                "outcome": e.outcome,
                "timestamp": e.recorded_at,
                "detail": e.detail,
            }
            for e in entries
        ],
        "count": len(entries),
        "filters": {"tenant_id": tenant_id, "outcome": outcome},
        "governed": True,
    }


# ═══ Audit View ═══


@router.get("/api/v1/console/audit")
def console_audit(
    tenant_id: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
):
    """Operator audit view — searchable event history."""
    deps.metrics.inc("requests_governed")
    entries = deps.audit_trail.query(
        tenant_id=tenant_id,
        action=action,
        outcome=outcome,
        limit=limit,
    )

    # Aggregate by action type
    action_counts: dict[str, int] = {}
    outcome_counts: dict[str, int] = {}
    actor_counts: dict[str, int] = {}
    for e in entries:
        action_counts[e.action] = action_counts.get(e.action, 0) + 1
        outcome_counts[e.outcome or "unknown"] = outcome_counts.get(e.outcome or "unknown", 0) + 1
        actor_counts[e.actor_id] = actor_counts.get(e.actor_id, 0) + 1

    return {
        "entries": [
            {
                "entry_id": e.entry_id,
                "action": e.action,
                "actor_id": e.actor_id,
                "tenant_id": e.tenant_id,
                "target": e.target,
                "outcome": e.outcome,
                "timestamp": e.recorded_at,
                "hash": e.entry_hash[:16],
            }
            for e in entries
        ],
        "count": len(entries),
        "aggregations": {
            "by_action": dict(sorted(action_counts.items(), key=lambda x: -x[1])[:10]),
            "by_outcome": outcome_counts,
            "by_actor": dict(sorted(actor_counts.items(), key=lambda x: -x[1])[:10]),
        },
        "chain_intact": deps.audit_trail.verify_chain(),
        "governed": True,
    }


# ═══ Checkpoints View ═══


@router.get("/api/v1/console/checkpoints")
def console_checkpoints():
    """Operator checkpoint view — coordination state snapshots."""
    deps.metrics.inc("requests_governed")
    coordination = deps.coordination_engine.summary()
    store_states = deps.coordination_store.list_states()
    return {
        "engine_state": coordination,
        "persisted_checkpoints": list(store_states),
        "checkpoint_count": len(store_states),
        "governed": True,
    }


# ═══ Providers View ═══


@router.get("/api/v1/console/providers")
def console_providers():
    """Operator provider view — LLM provider health and cost."""
    deps.metrics.inc("requests_governed")

    budget_summary = deps.llm_bridge.budget_summary()
    budgets = budget_summary.get("budgets", [])

    return {
        "providers": {
            "default_backend": "configured",
            "invocation_count": deps.llm_bridge.invocation_count,
            "total_cost": deps.llm_bridge.total_cost,
            "circuit_breaker": deps.llm_circuit.state.value,
        },
        "budgets": [
            {
                "budget_id": b.get("budget_id", ""),
                "spent": b.get("spent", 0),
                "max_cost": b.get("max_cost", 0),
                "calls_made": b.get("calls_made", 0),
                "exhausted": b.get("exhausted", False),
            }
            for b in budgets
        ] if isinstance(budgets, list) else [],
        "tenant_count": deps.tenant_budget_mgr.tenant_count(),
        "total_tenant_spend": deps.tenant_budget_mgr.total_spent(),
        "governed": True,
    }


# ═══ Scheduler View ═══


@router.get("/api/v1/console/scheduler")
def console_scheduler():
    """Operator scheduler view — jobs, execution history, health."""
    deps.metrics.inc("requests_governed")
    summary = deps.scheduler.summary()
    jobs = deps.scheduler.list_jobs()
    recent = deps.scheduler.recent_executions(limit=20)
    return {
        "summary": summary,
        "jobs": [
            {
                "job_id": j.job_id,
                "name": j.name,
                "schedule_type": j.schedule_type.value,
                "handler_name": j.handler_name,
                "enabled": j.enabled,
                "tenant_id": j.tenant_id,
            }
            for j in jobs
        ],
        "recent_executions": [
            {
                "execution_id": e.execution_id,
                "job_id": e.job_id,
                "status": e.status.value,
                "started_at": e.started_at,
                "error": e.error,
            }
            for e in recent
        ],
        "governed": True,
    }


# ═══ Full Console ═══


@router.get("/api/v1/console")
def full_console():
    """Complete operator console — all views in one call."""
    deps.metrics.inc("requests_governed")
    return {
        "home": console_home(),
        "checkpoints": console_checkpoints(),
        "providers": console_providers(),
        "scheduler": console_scheduler(),
        "governed": True,
    }
