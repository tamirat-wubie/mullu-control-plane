"""Multi-Agent Live Runtime — governed cooperation between external agents.

Enables multiple agents to delegate work, hand off context, and resolve
conflicts through governed HTTP endpoints. Every operation goes through
the coordination engine and audit trail.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


# ── Request Models ────────────────────────────────────────────────────


class DelegateRequest(BaseModel):
    delegation_id: str
    delegator_id: str
    delegate_id: str
    goal_id: str
    action_scope: str
    deadline: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResolveDelegationRequest(BaseModel):
    delegation_id: str
    status: str  # "accepted", "rejected", "expired"
    reason: str


class HandoffRequest(BaseModel):
    handoff_id: str
    from_party: str
    to_party: str
    goal_id: str
    context_ids: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordMergeRequest(BaseModel):
    merge_id: str
    goal_id: str
    source_ids: list[str]
    outcome: str  # "merged", "conflict_detected", "deferred"
    reason: str


class RecordConflictRequest(BaseModel):
    conflict_id: str
    goal_id: str
    conflicting_ids: list[str]
    strategy: str  # "prefer_latest", "prefer_highest_confidence", "escalate", "manual"
    resolved: bool = False
    resolution_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post("/api/v1/multi-agent/delegate")
def delegate_work(req: DelegateRequest):
    """Delegate work from one agent to another with governed tracking."""
    from mcoi_runtime.contracts.coordination import DelegationRequest
    deps.metrics.inc("requests_governed")
    try:
        delegation = DelegationRequest(
            delegation_id=req.delegation_id,
            delegator_id=req.delegator_id,
            delegate_id=req.delegate_id,
            goal_id=req.goal_id,
            action_scope=req.action_scope,
            deadline=req.deadline or None,
            metadata=req.metadata,
        )
        result = deps.coordination_engine.request_delegation(delegation)
    except (ValueError, Exception) as exc:
        raise HTTPException(400, detail={
            "error": "delegation failed",
            "error_code": "delegation_error",
            "governed": True,
        })
    deps.audit_trail.record(
        action="multi_agent.delegate",
        actor_id=req.delegator_id,
        tenant_id="",
        target=req.delegate_id,
        outcome="success",
        detail={"goal_id": req.goal_id, "scope": req.action_scope},
    )
    return {
        "delegation_id": result.delegation_id,
        "delegator_id": result.delegator_id,
        "delegate_id": result.delegate_id,
        "goal_id": result.goal_id,
        "governed": True,
    }


@router.post("/api/v1/multi-agent/delegate/resolve")
def resolve_delegation(req: ResolveDelegationRequest):
    """Resolve a delegation — accept, reject, or expire."""
    from mcoi_runtime.contracts.coordination import DelegationResult, DelegationStatus
    from datetime import datetime, timezone
    deps.metrics.inc("requests_governed")
    try:
        status = DelegationStatus(req.status)
    except ValueError:
        raise HTTPException(400, detail={
            "error": f"invalid status: {req.status}",
            "error_code": "invalid_status",
            "governed": True,
        })
    try:
        result = DelegationResult(
            delegation_id=req.delegation_id,
            status=status,
            reason=req.reason,
            resolved_at=datetime.now(timezone.utc).isoformat(),
        )
        deps.coordination_engine.resolve_delegation(result)
    except Exception:
        raise HTTPException(400, detail={
            "error": "resolution failed",
            "error_code": "resolution_error",
            "governed": True,
        })
    deps.audit_trail.record(
        action="multi_agent.delegate.resolve",
        actor_id="api",
        tenant_id="",
        target=req.delegation_id,
        outcome=req.status,
        detail={"reason": req.reason},
    )
    return {
        "delegation_id": req.delegation_id,
        "status": req.status,
        "governed": True,
    }


@router.post("/api/v1/multi-agent/handoff")
def record_handoff(req: HandoffRequest):
    """Record a governed agent-to-agent handoff with full context."""
    from mcoi_runtime.contracts.coordination import HandoffRecord
    from datetime import datetime, timezone
    deps.metrics.inc("requests_governed")
    try:
        handoff = HandoffRecord(
            handoff_id=req.handoff_id,
            from_party=req.from_party,
            to_party=req.to_party,
            goal_id=req.goal_id,
            context_ids=tuple(req.context_ids),
            handed_off_at=datetime.now(timezone.utc).isoformat(),
            metadata=req.metadata,
        )
        deps.coordination_engine.record_handoff(handoff)
    except Exception:
        raise HTTPException(400, detail={
            "error": "handoff failed",
            "error_code": "handoff_error",
            "governed": True,
        })
    deps.audit_trail.record(
        action="multi_agent.handoff",
        actor_id=req.from_party,
        tenant_id="",
        target=req.to_party,
        outcome="success",
        detail={"goal_id": req.goal_id, "context_count": len(req.context_ids)},
    )
    return {
        "handoff_id": req.handoff_id,
        "from_party": req.from_party,
        "to_party": req.to_party,
        "governed": True,
    }


@router.post("/api/v1/multi-agent/merge")
def record_merge(req: RecordMergeRequest):
    """Record a merge decision combining results from multiple agents."""
    from mcoi_runtime.contracts.coordination import MergeDecision, MergeOutcome
    from datetime import datetime, timezone
    deps.metrics.inc("requests_governed")
    try:
        outcome = MergeOutcome(req.outcome)
    except ValueError:
        raise HTTPException(400, detail={
            "error": f"invalid outcome: {req.outcome}",
            "error_code": "invalid_outcome",
            "governed": True,
        })
    try:
        merge = MergeDecision(
            merge_id=req.merge_id,
            goal_id=req.goal_id,
            source_ids=tuple(req.source_ids),
            outcome=outcome,
            reason=req.reason,
            resolved_at=datetime.now(timezone.utc).isoformat(),
        )
        deps.coordination_engine.record_merge(merge)
    except Exception:
        raise HTTPException(400, detail={
            "error": "merge recording failed",
            "error_code": "merge_error",
            "governed": True,
        })
    return {
        "merge_id": req.merge_id,
        "outcome": req.outcome,
        "governed": True,
    }


@router.post("/api/v1/multi-agent/conflict")
def record_conflict(req: RecordConflictRequest):
    """Record a conflict between agents for explicit resolution."""
    from mcoi_runtime.contracts.coordination import ConflictRecord, ConflictStrategy
    deps.metrics.inc("requests_governed")
    try:
        strategy = ConflictStrategy(req.strategy)
    except ValueError:
        raise HTTPException(400, detail={
            "error": f"invalid strategy: {req.strategy}",
            "error_code": "invalid_strategy",
            "governed": True,
        })
    try:
        conflict = ConflictRecord(
            conflict_id=req.conflict_id,
            goal_id=req.goal_id,
            conflicting_ids=tuple(req.conflicting_ids),
            strategy=strategy,
            resolved=req.resolved,
            resolution_id=req.resolution_id or None,
            metadata=req.metadata,
        )
        deps.coordination_engine.record_conflict(conflict)
    except Exception:
        raise HTTPException(400, detail={
            "error": "conflict recording failed",
            "error_code": "conflict_error",
            "governed": True,
        })
    return {
        "conflict_id": req.conflict_id,
        "strategy": req.strategy,
        "resolved": req.resolved,
        "governed": True,
    }


@router.get("/api/v1/multi-agent/conflicts/unresolved")
def unresolved_conflicts():
    """List unresolved conflicts requiring operator attention."""
    deps.metrics.inc("requests_governed")
    conflicts = deps.coordination_engine.list_unresolved_conflicts()
    return {
        "conflicts": [
            {
                "conflict_id": c.conflict_id,
                "goal_id": c.goal_id,
                "conflicting_ids": list(c.conflicting_ids),
                "strategy": c.strategy.value,
            }
            for c in conflicts
        ],
        "count": len(conflicts),
        "governed": True,
    }


@router.get("/api/v1/multi-agent/summary")
def multi_agent_summary():
    """Multi-agent runtime summary."""
    deps.metrics.inc("requests_governed")
    return {**deps.coordination_engine.summary(), "governed": True}
