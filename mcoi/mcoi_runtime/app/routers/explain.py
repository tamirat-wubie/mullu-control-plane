"""Explanation endpoints — why was this action allowed/denied?"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope

router = APIRouter()

_MAX_AUDIT_EXPLAIN_ENTRY_INDEX = 499


def _explain_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _raise_explain_audit_validation_error() -> None:
    raise HTTPException(
        422,
        detail=_explain_error_detail("invalid explain audit request", "explain_audit_invalid_request"),
    )


def _coerce_audit_entry_index(entry_index: object) -> int:
    if isinstance(entry_index, bool):
        _raise_explain_audit_validation_error()
    try:
        value = int(entry_index)
    except (TypeError, ValueError):
        _raise_explain_audit_validation_error()
    if str(entry_index).strip() != str(value):
        _raise_explain_audit_validation_error()
    if value < 0 or value > _MAX_AUDIT_EXPLAIN_ENTRY_INDEX:
        _raise_explain_audit_validation_error()
    return value


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
def explain_audit_entry(entry_index: str, request: Request):
    """Explain a specific audit trail entry by index."""
    deps.metrics.inc("requests_governed")
    read_index = _coerce_audit_entry_index(entry_index)
    entries = deps.audit_trail.query(limit=read_index + 1)
    if read_index >= len(entries):
        raise HTTPException(
            404,
            detail=_explain_error_detail("audit entry not found", "entry_not_found"),
        )
    entry = entries[read_index]
    enforce_tenant_scope(request, entry.tenant_id)
    explanation = deps.explanation_engine.explain_audit_entry(entry)
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
