"""Purpose: assistant kernel HTTP read and planning endpoints.
Governance scope: assistant profile read models, FinanceOps and TeamOps planning,
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

from typing import Any, Mapping

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from mcoi_runtime.app.cognitive_planning_integration import planning_context_for
from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope
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
    team_ops_default_profile,
    team_ops_shared_inbox_closure_contract,
    team_ops_shared_inbox_goal,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    RequestInterface,
    build_clarification_requests,
    build_draft_assistant_read_model,
    build_governed_team_assistant_pilot_read_model,
    build_personal_assistant_console_read_model,
    build_personal_assistant_preview_plan,
    build_personal_assistant_readiness_demo,
    build_teamops_gmail_live_probe_readiness,
    interpret_user_request,
    load_default_skill_registry,
)


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


class TeamOpsAssistantPlanRequest(BaseModel):
    """Request to compile a TeamOps shared-inbox plan without executing it."""

    tenant_id: str
    owner_id: str
    inbox_ref: str
    request_ref: str
    created_at: str = ""
    consent_scope: str = "shared_inbox_external_send"
    consent_granted_by: str = ""
    consent_expires_at: str = ""
    consent_evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PersonalAssistantPreviewRequest(BaseModel):
    """Request to interpret and preview a governed personal-assistant action."""

    user_request: str
    request_id: str = ""
    submitted_at: str = ""
    interface: str = RequestInterface.API_ROUTE.value
    connector_refs: list[dict[str, Any]] = Field(default_factory=list)
    thread_id: str = "thread-personal-assistant-preview"
    requested_from_id: str = "operator"
    include_console_read_model: bool = False


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


@router.get("/api/v1/personal-assistant/skills")
def personal_assistant_skill_read_model():
    """Return the governed personal-assistant skill registry read model."""
    _inc_metric("requests_governed")
    registry = load_default_skill_registry()
    return {
        "registry": registry.read_model(),
        "execution_allowed": False,
        "live_connector_execution_allowed": False,
        "governed": True,
    }


@router.get("/api/v1/personal-assistant/pilot/read-model")
def personal_assistant_pilot_read_model():
    """Return the no-effect governed Team Assistant pilot read model."""
    _inc_metric("requests_governed")
    generated_at = _clock_now()
    console_payload = build_personal_assistant_console_read_model(generated_at=generated_at)
    readiness_payload = build_personal_assistant_readiness_demo(
        generated_at=generated_at,
        console_payload=console_payload,
    )
    return build_governed_team_assistant_pilot_read_model(
        generated_at=generated_at,
        console_payload=console_payload,
        readiness_payload=readiness_payload,
        draft_payload=build_draft_assistant_read_model(generated_at=generated_at),
        teamops_live_probe_payload=build_teamops_gmail_live_probe_readiness(
            generated_at=generated_at,
        ),
    )


@router.post("/api/v1/personal-assistant/requests/preview")
def preview_personal_assistant_request(req: PersonalAssistantPreviewRequest):
    """Interpret a request and emit request, WHQR, plan, and receipt previews."""
    _inc_metric("requests_governed")
    try:
        now = req.submitted_at or _clock_now()
        request_id = req.request_id or _personal_assistant_request_id(req.user_request, now, req.interface)
        plan_id = _personal_assistant_plan_id(request_id)
        intent = interpret_user_request(
            req.user_request,
            request_id=request_id,
            submitted_at=now,
            interface=req.interface,
            connector_refs=tuple(req.connector_refs),
        )
        clarification_bundle = build_clarification_requests(
            intent,
            thread_id=req.thread_id,
            requested_from_id=req.requested_from_id,
            requested_at=now,
        )
        envelope = build_personal_assistant_preview_plan(intent, plan_id=plan_id, created_at=now)
    except (PersonalAssistantInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_assistant_error_detail(
                "invalid personal assistant preview",
                "invalid_personal_assistant_preview",
            ),
        ) from exc
    response: dict[str, Any] = {
        **envelope.as_dict(),
        "clarification_bundle": {
            "request_id": clarification_bundle.request_id,
            "clarifications": [request.to_json_dict() for request in clarification_bundle.clarifications],
            "clarification_count": len(clarification_bundle.clarifications),
        },
        "outcome": _personal_assistant_outcome(envelope.plan, clarification_bundle.empty),
        "effect_boundary": {
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "external_send_allowed": False,
            "connector_mutation_allowed": False,
            "memory_write_allowed": False,
            "deployment_mutation_allowed": False,
        },
    }
    if req.include_console_read_model:
        response["console_read_model"] = build_personal_assistant_console_read_model(
            generated_at=now,
            recent_requests=(
                {
                    "request_id": envelope.request["request_id"],
                    "summary": envelope.request["user_goal"],
                    "status": envelope.plan["mode"],
                },
            ),
            receipts=(envelope.receipt,),
        )
    return response


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
        consent_ledger = _consent_ledger_from_request(
            req,
            goal_created_at=now,
            capability_id="payment.execute.with_approval",
        )
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


@router.post("/api/v1/assistant/team-ops/plans")
def compile_team_ops_assistant_plan(req: TeamOpsAssistantPlanRequest, request: Request):
    """Compile a TeamOps shared-inbox plan without executing effects."""
    _inc_metric("requests_governed")
    enforce_tenant_scope(request, req.tenant_id)
    try:
        now = req.created_at or _clock_now()
        profile = team_ops_default_profile()
        goal = team_ops_shared_inbox_goal(
            tenant_id=req.tenant_id,
            owner_id=req.owner_id,
            profile_id=profile.assistant_id,
            inbox_ref=req.inbox_ref,
            request_ref=req.request_ref,
            created_at=now,
        )
        consent_ledger = _consent_ledger_from_request(
            req,
            goal_created_at=now,
            capability_id="email.send.with_approval",
        )
        closure_contract = team_ops_shared_inbox_closure_contract(goal.goal_id)
        plan = AssistantKernel().compile_plan(
            profile=profile,
            goal=goal,
            closure_contract=closure_contract,
            consent_ledger=consent_ledger,
            now=now,
        )
    except RuntimeCoreInvariantError as exc:
        raise HTTPException(400, detail=_assistant_error_detail("invalid assistant plan", "invalid_assistant_plan")) from exc

    cognitive_context = planning_context_for(deps, tuple(step.capability_id for step in plan.steps))
    response = {
        "profile": profile.to_dict(),
        "goal": goal.to_dict(),
        "plan": plan.to_dict(),
        "operator_queue_item": _operator_queue_item(
            plan=plan,
            tenant_id=req.tenant_id,
            owner_id=req.owner_id,
            cognitive_context=cognitive_context,
        ),
        "outcome": "AwaitingEvidence" if plan.blocked else "SolvedUnverified",
        "governed": True,
    }
    if cognitive_context is not None:
        response["cognitive_planning_context"] = cognitive_context
    return response


def _consent_ledger_from_request(
    req: FinanceOpsAssistantPlanRequest | TeamOpsAssistantPlanRequest,
    *,
    goal_created_at: str,
    capability_id: str,
) -> ConsentLedger | None:
    if not req.consent_evidence_refs:
        return None
    ledger = ConsentLedger()
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


def _personal_assistant_request_id(user_request: str, submitted_at: str, interface: str) -> str:
    return "pa_request_" + stable_identifier(
        "personal-assistant-request",
        {"user_request": user_request, "submitted_at": submitted_at, "interface": interface},
    )


def _personal_assistant_plan_id(request_id: str) -> str:
    return "pa_plan_" + stable_identifier("personal-assistant-plan", {"request_id": request_id})


def _personal_assistant_outcome(plan: Mapping[str, Any], clarification_complete: bool) -> str:
    if not clarification_complete:
        return "AwaitingEvidence"
    if bool(plan.get("requires_approval")):
        return "AwaitingEvidence"
    return "SolvedVerified"
