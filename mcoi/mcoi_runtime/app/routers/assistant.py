"""Purpose: assistant kernel HTTP read and planning endpoints.
Governance scope: assistant profile read models, FinanceOps planning,
    consent binding, approval controls, idempotency controls, and closure
    contract projection.
Dependencies: FastAPI, router deps, and mcoi_runtime.assistant_kernel.
Test contract: mcoi/tests/test_assistant_router.py.
Invariants:
  - Routes compile plans only; no connector, payment, email, or calendar effect
    is executed here.
  - External-effect plans require active consent evidence.
  - Every response is governed and exposes blocked reasons explicitly.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.cognitive_planning_integration import planning_context_for
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.assistant_kernel import (
    AssistantKernel,
    ConsentGrant,
    ConsentLedger,
    builtin_assistant_profiles,
    consent_grant_id,
    finance_ops_default_profile,
    finance_ops_invoice_payment_goal,
    finance_ops_payment_closure_contract,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


router = APIRouter()


class FinanceOpsAssistantPlanRequest(BaseModel):
    """Request to compile a FinanceOps assistant plan without executing it."""

    tenant_id: str
    owner_id: str
    invoice_ref: str
    vendor_ref: str
    created_at: str = ""
    consent_scope: str = "invoice_payment"
    consent_granted_by: str = ""
    consent_expires_at: str = ""
    consent_evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _clock_now() -> str:
    try:
        return deps.clock()
    except RuntimeError:
        return "2026-05-13T00:00:00+00:00"


def _inc_metric(name: str) -> None:
    try:
        deps.metrics.inc(name)
    except RuntimeError:
        return


def _assistant_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


@router.get("/api/v1/assistant/profiles")
def assistant_profiles_read_model():
    """Return the built-in governed assistant profile catalog."""
    _inc_metric("requests_governed")
    profiles = tuple(profile.to_dict() for profile in builtin_assistant_profiles())
    return {
        "profiles": profiles,
        "count": len(profiles),
        "governed": True,
    }


@router.post("/api/v1/assistant/finance-ops/plans")
def compile_finance_ops_assistant_plan(req: FinanceOpsAssistantPlanRequest):
    """Compile a FinanceOps invoice-payment plan without executing effects."""
    _inc_metric("requests_governed")
    try:
        now = req.created_at or _clock_now()
        profile = finance_ops_default_profile()
        goal = finance_ops_invoice_payment_goal(
            tenant_id=req.tenant_id,
            owner_id=req.owner_id,
            profile_id=profile.assistant_id,
            invoice_ref=req.invoice_ref,
            vendor_ref=req.vendor_ref,
            created_at=now,
        )
        consent_ledger = _consent_ledger_from_request(req, goal_created_at=now)
        closure_contract = finance_ops_payment_closure_contract(goal.goal_id)
        plan = AssistantKernel().compile_plan(
            profile=profile,
            goal=goal,
            closure_contract=closure_contract,
            consent_ledger=consent_ledger,
            now=now,
        )
    except RuntimeCoreInvariantError as exc:
        raise HTTPException(400, detail=_assistant_error_detail("invalid assistant plan", "invalid_assistant_plan")) from exc

    # Plan-time cognitive read-back (default-OFF). Read-only advisory; None when
    # disabled => the response is byte-identical. Never mutates the governed plan.
    cognitive_context = planning_context_for(deps, tuple(step.capability_id for step in plan.steps))
    response = {
        "profile": profile.to_dict(),
        "goal": goal.to_dict(),
        "plan": plan.to_dict(),
        "operator_queue_item": _operator_queue_item(
            plan=plan, tenant_id=req.tenant_id, owner_id=req.owner_id, cognitive_context=cognitive_context
        ),
        "outcome": "AwaitingEvidence" if plan.blocked else "SolvedUnverified",
        "governed": True,
    }
    if cognitive_context is not None:
        response["cognitive_planning_context"] = cognitive_context
    return response


def _consent_ledger_from_request(
    req: FinanceOpsAssistantPlanRequest,
    *,
    goal_created_at: str,
) -> ConsentLedger | None:
    if not req.consent_evidence_refs:
        return None
    ledger = ConsentLedger()
    capability_id = "payment.execute.with_approval"
    granted_by = req.consent_granted_by or req.owner_id
    expires_at = req.consent_expires_at or goal_created_at
    ledger.grant(
        ConsentGrant(
            consent_id=consent_grant_id(
                tenant_id=req.tenant_id,
                owner_id=req.owner_id,
                capability_id=capability_id,
                scope=req.consent_scope,
                granted_at=goal_created_at,
            ),
            tenant_id=req.tenant_id,
            owner_id=req.owner_id,
            capability_id=capability_id,
            scope=req.consent_scope,
            granted_by=granted_by,
            granted_at=goal_created_at,
            expires_at=expires_at,
            evidence_refs=tuple(req.consent_evidence_refs),
            metadata={"request_metadata": dict(req.metadata)},
        )
    )
    return ledger


def _operator_queue_item(
    *, plan: Any, tenant_id: str, owner_id: str, cognitive_context: dict | None = None
) -> dict[str, Any]:
    queue_state = "blocked" if plan.blocked else "ready_for_governed_dispatch"
    queue_id = stable_identifier(
        "assistant-operator-queue",
        {
            "plan_id": plan.plan_id,
            "tenant_id": tenant_id,
            "owner_id": owner_id,
            "queue_state": queue_state,
        },
    )
    item = {
        "queue_id": queue_id,
        "plan_id": plan.plan_id,
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "state": queue_state,
        "blocked_reasons": list(plan.blocked_reasons),
        "required_controls": list(plan.required_controls),
        "step_count": len(plan.steps),
        "execution_authority_granted": False,
    }
    # Advisory only; never changes queue identity (queue_id excludes it).
    if cognitive_context is not None:
        item["cognitive_planning_context"] = cognitive_context
    return item
