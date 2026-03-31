"""Runbook learning endpoints — detect patterns, promote, approve, activate."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


class PromoteRunbookRequest(BaseModel):
    pattern_id: str
    name: str
    description: str = ""
    policy_pack_id: str = "default"


class ApproveRunbookRequest(BaseModel):
    runbook_id: str
    approved_by: str


@router.post("/api/v1/runbooks/analyze")
def analyze_patterns(limit: int = 200):
    """Scan audit trail for repeated successful execution patterns."""
    deps.metrics.inc("requests_governed")
    entries = deps.audit_trail.query(limit=limit)
    patterns = deps.runbook_learning.analyze(entries)
    return {
        "patterns": [
            {
                "pattern_id": p.pattern_id,
                "action_sequence": list(p.action_sequence),
                "occurrences": p.occurrence_count,
                "success_rate": p.success_rate,
                "tenants": list(p.tenant_ids),
            }
            for p in patterns
        ],
        "count": len(patterns),
        "governed": True,
    }


@router.post("/api/v1/runbooks/promote")
def promote_pattern(req: PromoteRunbookRequest):
    """Create a candidate runbook from a detected pattern."""
    deps.metrics.inc("requests_governed")
    try:
        runbook = deps.runbook_learning.promote(
            req.pattern_id, req.name, req.description, req.policy_pack_id,
        )
    except ValueError as exc:
        raise HTTPException(404, detail={
            "error": str(exc),
            "error_code": "pattern_not_found",
            "governed": True,
        })
    deps.audit_trail.record(
        action="runbook.promote",
        actor_id="api",
        tenant_id="system",
        target=runbook.runbook_id,
        outcome="success",
        detail={"pattern_id": req.pattern_id, "name": req.name},
    )
    return {
        "runbook_id": runbook.runbook_id,
        "name": runbook.name,
        "status": runbook.status.value,
        "action_sequence": list(runbook.action_sequence),
        "governed": True,
    }


@router.post("/api/v1/runbooks/approve")
def approve_runbook(req: ApproveRunbookRequest):
    """Operator approves a candidate runbook."""
    deps.metrics.inc("requests_governed")
    try:
        runbook = deps.runbook_learning.approve(req.runbook_id, req.approved_by)
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": str(exc),
            "error_code": "approval_failed",
            "governed": True,
        })
    deps.audit_trail.record(
        action="runbook.approve",
        actor_id=req.approved_by,
        tenant_id="system",
        target=req.runbook_id,
        outcome="success",
    )
    return {
        "runbook_id": runbook.runbook_id,
        "status": runbook.status.value,
        "approved_by": runbook.approved_by,
        "governed": True,
    }


@router.post("/api/v1/runbooks/{runbook_id}/activate")
def activate_runbook(runbook_id: str):
    """Activate an approved runbook."""
    deps.metrics.inc("requests_governed")
    try:
        deps.runbook_learning.activate(runbook_id)
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": str(exc),
            "error_code": "activation_failed",
            "governed": True,
        })
    return {"runbook_id": runbook_id, "status": "active", "governed": True}


@router.post("/api/v1/runbooks/{runbook_id}/retire")
def retire_runbook(runbook_id: str):
    """Retire an active runbook."""
    deps.metrics.inc("requests_governed")
    try:
        deps.runbook_learning.retire(runbook_id)
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": str(exc),
            "error_code": "retire_failed",
            "governed": True,
        })
    return {"runbook_id": runbook_id, "status": "retired", "governed": True}


@router.get("/api/v1/runbooks")
def list_runbooks(status: str = ""):
    """List runbooks, optionally filtered by status."""
    from mcoi_runtime.core.runbook_learning import RunbookStatus
    deps.metrics.inc("requests_governed")
    filter_status = None
    if status:
        try:
            filter_status = RunbookStatus(status)
        except ValueError:
            pass
    runbooks = deps.runbook_learning.list_runbooks(status=filter_status)
    return {
        "runbooks": [
            {
                "runbook_id": r.runbook_id,
                "name": r.name,
                "status": r.status.value,
                "action_sequence": list(r.action_sequence),
                "success_rate": r.success_rate,
                "occurrences": r.occurrence_count,
            }
            for r in runbooks
        ],
        "count": len(runbooks),
        "governed": True,
    }


@router.get("/api/v1/runbooks/patterns")
def list_patterns(limit: int = 50):
    """List detected execution patterns."""
    deps.metrics.inc("requests_governed")
    patterns = deps.runbook_learning.list_patterns(limit=limit)
    return {
        "patterns": [
            {
                "pattern_id": p.pattern_id,
                "action_sequence": list(p.action_sequence),
                "occurrences": p.occurrence_count,
                "success_rate": p.success_rate,
            }
            for p in patterns
        ],
        "count": len(patterns),
        "governed": True,
    }


@router.get("/api/v1/runbooks/summary")
def runbooks_summary():
    """Runbook learning engine summary."""
    deps.metrics.inc("requests_governed")
    return {**deps.runbook_learning.summary(), "governed": True}
