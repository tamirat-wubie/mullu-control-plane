"""Explanation endpoints — why was this action allowed/denied?"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


class ExplainActionRequest(BaseModel):
    action_type: str
    target: str
    tenant_id: str = ""
    budget_id: str = ""
    actor_id: str = ""


@router.post("/api/v1/explain/action")
def explain_action(req: ExplainActionRequest):
    """Explain what would happen if this action ran — which guards, which policy."""
    deps.metrics.inc("requests_governed")
    explanation = deps.explanation_engine.explain_action(
        req.action_type, req.target,
        tenant_id=req.tenant_id,
        budget_id=req.budget_id,
        actor_id=req.actor_id,
    )
    return {
        "explanation_id": explanation.explanation_id,
        "action": explanation.action,
        "target": explanation.target,
        "decision": explanation.decision,
        "reasons": explanation.reasons,
        "guard_chain_path": explanation.guard_chain_path,
        "policy_context": explanation.policy_context,
        "cost_context": explanation.cost_context,
        "governed": True,
    }


@router.get("/api/v1/explain/audit/{entry_index}")
def explain_audit_entry(entry_index: int):
    """Explain a specific audit trail entry by index."""
    deps.metrics.inc("requests_governed")
    entries = deps.audit_trail.query(limit=entry_index + 1)
    if entry_index >= len(entries):
        raise HTTPException(404, detail={
            "error": "audit entry not found",
            "error_code": "entry_not_found",
            "governed": True,
        })
    explanation = deps.explanation_engine.explain_audit_entry(entries[entry_index])
    return {
        "explanation_id": explanation.explanation_id,
        "action": explanation.action,
        "actor_id": explanation.actor_id,
        "target": explanation.target,
        "decision": explanation.decision,
        "reasons": explanation.reasons,
        "policy_context": explanation.policy_context,
        "governed": True,
    }


@router.get("/api/v1/explain/summary")
def explain_summary():
    """Explanation engine summary."""
    deps.metrics.inc("requests_governed")
    return {**deps.explanation_engine.summary(), "governed": True}
