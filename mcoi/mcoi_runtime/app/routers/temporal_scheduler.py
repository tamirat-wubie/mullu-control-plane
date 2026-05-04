"""Purpose: temporal scheduler HTTP endpoints.
Governance scope: create/list/get/tick scheduled temporal actions with
    explicit runtime-owned time fields and bounded execution receipts.
Dependencies: router deps, temporal scheduler engine, store, and worker.
Invariants:
  - Scheduled actions require execute_at.
  - Worker tick only executes through lease and temporal policy re-check.
  - Responses expose bounded receipt/proof identifiers, not handler internals.
  - All endpoint responses carry governed=True.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.contracts.temporal_runtime import TemporalActionRequest, TemporalRiskLevel
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.temporal_scheduler import ScheduledActionState
from mcoi_runtime.core.temporal_scheduler_worker import TemporalSchedulerWorker
from mcoi_runtime.persistence.errors import PersistenceError

router = APIRouter()


def _temporal_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


class TemporalScheduleRequest(BaseModel):
    schedule_id: str
    action_id: str
    tenant_id: str
    actor_id: str
    action_type: str
    execute_at: str
    requested_at: str = ""
    risk: str = TemporalRiskLevel.LOW.value
    not_before: str = ""
    expires_at: str = ""
    approval_expires_at: str = ""
    evidence_fresh_until: str = ""
    retry_after: str = ""
    max_attempts: int = 0
    attempt_count: int = 0
    handler_name: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemporalWorkerTickRequest(BaseModel):
    worker_id: str = "temporal-worker"
    limit: int = 10
    lease_seconds: int = 60
    certify_proofs: bool = True


def _clock_now() -> str:
    return deps.clock()


def _schedule_to_body(schedule: Any) -> dict[str, Any]:
    return {
        "schedule_id": schedule.schedule_id,
        "tenant_id": schedule.tenant_id,
        "action_id": schedule.action.action_id,
        "action_type": schedule.action.action_type,
        "execute_at": schedule.execute_at,
        "state": schedule.state.value,
        "handler_name": schedule.handler_name,
        "created_at": schedule.created_at,
        "updated_at": schedule.updated_at,
        "metadata": dict(schedule.metadata),
    }


def _receipt_to_body(receipt: Any) -> dict[str, Any]:
    return {
        "receipt_id": receipt.receipt_id,
        "schedule_id": receipt.schedule_id,
        "tenant_id": receipt.tenant_id,
        "verdict": receipt.verdict.value,
        "reason": receipt.reason,
        "evaluated_at": receipt.evaluated_at,
        "worker_id": receipt.worker_id,
        "temporal_decision_id": receipt.temporal_decision_id,
        "temporal_verdict": receipt.temporal_verdict,
    }


@router.post("/api/v1/temporal/schedules")
def create_temporal_schedule(req: TemporalScheduleRequest):
    """Create a governed temporal action schedule."""
    deps.metrics.inc("requests_governed")
    try:
        risk = TemporalRiskLevel(req.risk)
    except ValueError:
        raise HTTPException(400, detail=_temporal_error_detail("invalid risk", "invalid_risk"))
    try:
        action = TemporalActionRequest(
            action_id=req.action_id,
            tenant_id=req.tenant_id,
            actor_id=req.actor_id,
            action_type=req.action_type,
            risk=risk,
            requested_at=req.requested_at or _clock_now(),
            execute_at=req.execute_at,
            not_before=req.not_before,
            expires_at=req.expires_at,
            approval_expires_at=req.approval_expires_at,
            evidence_fresh_until=req.evidence_fresh_until,
            retry_after=req.retry_after,
            max_attempts=req.max_attempts,
            attempt_count=req.attempt_count,
            metadata=req.metadata,
        )
        schedule = deps.temporal_scheduler.register(
            req.schedule_id,
            action,
            handler_name=req.handler_name,
            metadata=req.metadata,
        )
        deps.temporal_scheduler_store.save_action(schedule)
    except (RuntimeCoreInvariantError, ValueError, PersistenceError) as exc:
        raise HTTPException(400, detail=_temporal_error_detail(str(exc), "invalid_temporal_schedule")) from exc
    return {"schedule": _schedule_to_body(schedule), "governed": True}


@router.get("/api/v1/temporal/schedules")
def list_temporal_schedules(
    tenant_id: str = "",
    state: str = "",
):
    """List temporal schedules from the persistent store."""
    deps.metrics.inc("requests_governed")
    try:
        state_filter = ScheduledActionState(state) if state else None
    except ValueError:
        raise HTTPException(400, detail=_temporal_error_detail("invalid state", "invalid_state"))
    schedules = deps.temporal_scheduler_store.list_actions(
        tenant_id=tenant_id,
        state=state_filter,
    )
    return {
        "schedules": [_schedule_to_body(schedule) for schedule in schedules],
        "count": len(schedules),
        "governed": True,
    }


@router.get("/api/v1/temporal/schedules/{schedule_id}")
def get_temporal_schedule(schedule_id: str):
    """Return one temporal schedule and its receipts."""
    deps.metrics.inc("requests_governed")
    schedule = deps.temporal_scheduler_store.get_action(schedule_id)
    if schedule is None:
        raise HTTPException(404, detail=_temporal_error_detail("schedule not found", "schedule_not_found"))
    receipts = deps.temporal_scheduler_store.list_receipts(schedule_id=schedule_id)
    return {
        "schedule": _schedule_to_body(schedule),
        "receipts": [_receipt_to_body(receipt) for receipt in receipts],
        "receipt_count": len(receipts),
        "governed": True,
    }


@router.post("/api/v1/temporal/schedules/{schedule_id}/cancel")
def cancel_temporal_schedule(schedule_id: str, worker_id: str = "temporal-api"):
    """Cancel a temporal schedule and persist a cancellation receipt."""
    deps.metrics.inc("requests_governed")
    try:
        receipt = deps.temporal_scheduler.mark_cancelled(schedule_id, worker_id=worker_id)
        schedule = deps.temporal_scheduler.get(schedule_id)
        deps.temporal_scheduler_store.append_receipt(receipt)
        deps.temporal_scheduler_store.save_action(schedule)
        proof = deps.proof_bridge.certify_temporal_run_receipt(
            scheduled_action=schedule,
            run_receipt=receipt,
            actor_id=worker_id,
        )
    except RuntimeCoreInvariantError as exc:
        raise HTTPException(404, detail=_temporal_error_detail(str(exc), "schedule_not_found")) from exc
    except (ValueError, PersistenceError) as exc:
        raise HTTPException(400, detail=_temporal_error_detail(str(exc), "temporal_cancel_failed")) from exc
    return {
        "schedule": _schedule_to_body(schedule),
        "receipt": _receipt_to_body(receipt),
        "proof_receipt_id": proof.capsule.receipt.receipt_id,
        "governed": True,
    }


@router.post("/api/v1/temporal/worker/tick")
def tick_temporal_worker(req: TemporalWorkerTickRequest):
    """Run one bounded temporal scheduler worker tick."""
    deps.metrics.inc("requests_governed")
    try:
        worker = TemporalSchedulerWorker(
            scheduler=deps.temporal_scheduler,
            store=deps.temporal_scheduler_store,
            worker_id=req.worker_id,
            handlers=deps.temporal_action_handlers,
            proof_bridge=deps.proof_bridge if req.certify_proofs else None,
            lease_seconds=req.lease_seconds,
        )
        results = worker.run_once(limit=req.limit)
    except (TypeError, ValueError, PersistenceError) as exc:
        raise HTTPException(400, detail=_temporal_error_detail(str(exc), "temporal_worker_error")) from exc
    return {
        "results": [
            {
                "schedule_id": result.schedule_id,
                "worker_id": result.worker_id,
                "evaluation_receipt": _receipt_to_body(result.evaluation_receipt),
                "closure_receipt": (
                    _receipt_to_body(result.closure_receipt)
                    if result.closure_receipt is not None
                    else None
                ),
                "proof_receipt_ids": [
                    proof.capsule.receipt.receipt_id
                    for proof in result.proofs
                ],
            }
            for result in results
        ],
        "count": len(results),
        "summary": deps.temporal_scheduler_store.summary(),
        "governed": True,
    }


@router.get("/api/v1/temporal/summary")
def temporal_scheduler_summary():
    """Return temporal scheduler runtime and persistence summaries."""
    deps.metrics.inc("requests_governed")
    return {
        "runtime": deps.temporal_scheduler.summary(),
        "store": deps.temporal_scheduler_store.summary(),
        "governed": True,
    }
