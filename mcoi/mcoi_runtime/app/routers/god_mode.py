"""God-mode HTTP surface — capability catalog, agreements, tickets, receipts.

Every privileged ("god") capability ships DORMANT. To make one invocable,
an authorized operator records a registration agreement via this router.
At invocation time, a separate per-call activation agreement is required
which materializes as a single-use, time-bounded ticket.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.auth_context import bind_claimed_actor
from mcoi_runtime.app.routers.musia_auth import require_admin
from mcoi_runtime.contracts.god_mode import GodReceiptOutcome
from mcoi_runtime.core.god_mode_engine import (
    GodModeEngineError,
    get_engine,
)
from mcoi_runtime.core.god_mode_integration import (
    install_default_capabilities,
)
from mcoi_runtime.core.god_mode_registry import (
    GodModeRegistryError,
    get_registry,
)


router = APIRouter()


# --- Request models ---------------------------------------------------------


class AgreeToRegisterRequest(BaseModel):
    actor_id: str = Field(..., min_length=1)
    justification: str = Field(..., min_length=1)


class WithdrawRegistrationRequest(BaseModel):
    actor_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class IssueTicketRequest(BaseModel):
    actor_id: str = Field(..., min_length=1)
    justification: str = Field(..., min_length=1)
    target: dict[str, str] = Field(default_factory=dict)
    ttl_seconds: int | None = None
    tenant_id: str = ""


class ConsumeTicketRequest(BaseModel):
    outcome: str = Field(..., min_length=1)
    pre_state: Any = None
    post_state: Any = None
    detail: dict[str, str] = Field(default_factory=dict)
    failure_reason: str = ""
    expected_tenant_id: str | None = None


class RevokeTicketRequest(BaseModel):
    actor_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class SuspendCapabilityRequest(BaseModel):
    actor_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


# --- Helpers ----------------------------------------------------------------


def _capability_view(module: str, name: str) -> dict[str, Any]:
    registry = get_registry()
    cap = registry.get_capability(module, name)
    state = registry.state_of(module, name)
    active = [a.to_json_dict() for a in registry.iter_active_agreements(module, name)]
    return {
        "capability": cap.to_json_dict(),
        "state": state.value,
        "active_agreements": active,
        "history_count": len(registry.list_agreements(module, name)),
        "pending_required_actors": registry.pending_required_actors(module, name),
    }


def _ensure_seeded() -> None:
    """Lazy seed of default proposals — keeps router usable without server.py."""
    if not get_registry().list_capabilities():
        install_default_capabilities()


def _god_mode_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _god_mode_public_error(exc: Exception, fallback: str) -> str:
    reason = str(exc).lower()
    if "dual control" in reason:
        return "dual control registration agreement failed"
    if "pending_dual" in reason:
        return "ticket issue blocked: pending_dual"
    if "bound to tenant" in reason:
        return "ticket consume blocked: bound to tenant"
    return fallback


# --- Catalog ----------------------------------------------------------------


@router.get("/api/v1/god-mode/capabilities")
def list_capabilities(module: str | None = None) -> dict[str, Any]:
    _ensure_seeded()
    registry = get_registry()
    items = []
    for cap in registry.list_capabilities():
        if module is not None and cap.module != module:
            continue
        items.append(_capability_view(cap.module, cap.name))
    return {"governed": True, "count": len(items), "capabilities": items}


@router.get("/api/v1/god-mode/health")
def god_mode_health() -> dict[str, Any]:
    """Operator visibility: capability counts by state."""
    _ensure_seeded()
    registry = get_registry()
    engine = get_engine()
    capabilities = registry.list_capabilities()
    by_state: dict[str, int] = {"dormant": 0, "armed": 0, "suspended": 0, "withdrawn": 0}
    by_blast_armed: dict[str, int] = {}
    for cap in capabilities:
        state = registry.state_of(cap.module, cap.name).value
        by_state[state] = by_state.get(state, 0) + 1
        if state == "armed":
            blast = cap.blast_radius.value
            by_blast_armed[blast] = by_blast_armed.get(blast, 0) + 1
    active_tickets = engine.list_tickets(active_only=True)
    return {
        "governed": True,
        "capability_count": len(capabilities),
        "by_state": by_state,
        "armed_by_blast_radius": by_blast_armed,
        "active_ticket_count": len(active_tickets),
        "receipt_count": len(engine.list_receipts()),
    }


@router.get("/api/v1/god-mode/modules")
def list_modules() -> dict[str, Any]:
    _ensure_seeded()
    registry = get_registry()
    modules = []
    for module_name in registry.list_modules():
        caps = [c for c in registry.list_capabilities() if c.module == module_name]
        armed = sum(1 for c in caps if registry.is_armed(c.module, c.name))
        modules.append(
            {
                "module": module_name,
                "capability_count": len(caps),
                "armed_count": armed,
            }
        )
    return {"governed": True, "modules": modules}


@router.get("/api/v1/god-mode/capabilities/{module}/{name}")
def get_capability(module: str, name: str) -> dict[str, Any]:
    _ensure_seeded()
    try:
        return _capability_view(module, name)
    except GodModeRegistryError as exc:
        raise HTTPException(
            status_code=404,
            detail=_god_mode_error_detail("capability not found", "capability_not_found"),
        ) from exc


# --- Registration agreements ------------------------------------------------


@router.post("/api/v1/god-mode/capabilities/{module}/{name}/agree-to-register")
def agree_to_register(
    module: str, name: str, req: AgreeToRegisterRequest, request: Request
) -> dict[str, Any]:
    _ensure_seeded()
    actor_id = bind_claimed_actor(request, req.actor_id)
    try:
        agreement = get_registry().agree_to_register(
            module=module,
            name=name,
            actor_id=actor_id,
            justification=req.justification,
        )
    except GodModeRegistryError as exc:
        raise HTTPException(
            status_code=400,
            detail=_god_mode_error_detail(
                _god_mode_public_error(exc, "registration agreement failed"),
                "registration_agreement_failed",
            ),
        ) from exc
    return {
        "governed": True,
        "agreement": agreement.to_json_dict(),
        "state": get_registry().state_of(module, name).value,
    }


@router.post("/api/v1/god-mode/agreements/{agreement_id}/withdraw")
def withdraw_agreement(
    agreement_id: str, req: WithdrawRegistrationRequest, request: Request
) -> dict[str, Any]:
    actor_id = bind_claimed_actor(request, req.actor_id)
    try:
        withdrawn = get_registry().withdraw_registration(
            agreement_id=agreement_id,
            actor_id=actor_id,
            reason=req.reason,
        )
    except GodModeRegistryError as exc:
        raise HTTPException(
            status_code=400,
            detail=_god_mode_error_detail("registration withdrawal failed", "registration_withdrawal_failed"),
        ) from exc
    return {
        "governed": True,
        "agreement": withdrawn.to_json_dict(),
        "state": get_registry()
        .state_of(withdrawn.capability_module, withdrawn.capability_name)
        .value,
    }


@router.post("/api/v1/god-mode/capabilities/{module}/{name}/suspend")
def suspend_capability(
    module: str, name: str, req: SuspendCapabilityRequest, request: Request
) -> dict[str, Any]:
    actor_id = bind_claimed_actor(request, req.actor_id)
    try:
        get_registry().suspend(module, name)
    except GodModeRegistryError as exc:
        raise HTTPException(
            status_code=404,
            detail=_god_mode_error_detail("capability not found", "capability_not_found"),
        ) from exc
    return {
        "governed": True,
        "module": module,
        "name": name,
        "state": get_registry().state_of(module, name).value,
        "actor_id": actor_id,
        "reason": req.reason,
    }


@router.post("/api/v1/god-mode/capabilities/{module}/{name}/resume")
def resume_capability(module: str, name: str) -> dict[str, Any]:
    get_registry().resume(module, name)
    try:
        state = get_registry().state_of(module, name).value
    except GodModeRegistryError as exc:
        raise HTTPException(
            status_code=404,
            detail=_god_mode_error_detail("capability not found", "capability_not_found"),
        ) from exc
    return {"governed": True, "module": module, "name": name, "state": state}


# --- Tickets ----------------------------------------------------------------


@router.post("/api/v1/god-mode/capabilities/{module}/{name}/issue-ticket")
def issue_ticket(
    module: str, name: str, req: IssueTicketRequest, request: Request,
    _: str = Depends(require_admin),
) -> dict[str, Any]:
    _ensure_seeded()
    actor_id = bind_claimed_actor(request, req.actor_id)
    try:
        ticket, agreement = get_engine().issue_ticket(
            actor_id=actor_id,
            module=module,
            name=name,
            justification=req.justification,
            target=req.target,
            ttl_seconds=req.ttl_seconds,
            tenant_id=req.tenant_id,
        )
    except GodModeEngineError as exc:
        raise HTTPException(
            status_code=400,
            detail=_god_mode_error_detail(
                _god_mode_public_error(exc, "ticket issue failed"),
                "ticket_issue_failed",
            ),
        ) from exc
    return {
        "governed": True,
        "ticket": ticket.to_json_dict(),
        "agreement": agreement.to_json_dict(),
    }


@router.get("/api/v1/god-mode/tickets")
def list_tickets(
    actor_id: str | None = None,
    module: str | None = None,
    name: str | None = None,
    tenant_id: str | None = None,
    active_only: bool = False,
) -> dict[str, Any]:
    tickets = get_engine().list_tickets(
        actor_id=actor_id,
        module=module,
        name=name,
        tenant_id=tenant_id,
        active_only=active_only,
    )
    return {
        "governed": True,
        "count": len(tickets),
        "tickets": [t.to_json_dict() for t in tickets],
    }


@router.get("/api/v1/god-mode/tickets/{ticket_id}")
def get_ticket(ticket_id: str) -> dict[str, Any]:
    try:
        ticket = get_engine().get_ticket(ticket_id)
    except GodModeEngineError as exc:
        raise HTTPException(
            status_code=404,
            detail=_god_mode_error_detail("ticket not found", "ticket_not_found"),
        ) from exc
    return {"governed": True, "ticket": ticket.to_json_dict()}


@router.post("/api/v1/god-mode/tickets/{ticket_id}/consume")
def consume_ticket(ticket_id: str, req: ConsumeTicketRequest) -> dict[str, Any]:
    try:
        outcome = GodReceiptOutcome(req.outcome)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_god_mode_error_detail("invalid outcome", "invalid_outcome"),
        ) from exc
    try:
        receipt = get_engine().consume(
            ticket_id=ticket_id,
            outcome=outcome,
            pre_state=req.pre_state,
            post_state=req.post_state,
            detail=req.detail,
            failure_reason=req.failure_reason,
            expected_tenant_id=req.expected_tenant_id,
        )
    except GodModeEngineError as exc:
        raise HTTPException(
            status_code=400,
            detail=_god_mode_error_detail(
                _god_mode_public_error(exc, "ticket consume failed"),
                "ticket_consume_failed",
            ),
        ) from exc
    return {"governed": True, "receipt": receipt.to_json_dict()}


@router.post("/api/v1/god-mode/tickets/{ticket_id}/revoke")
def revoke_ticket(ticket_id: str, req: RevokeTicketRequest, request: Request) -> dict[str, Any]:
    actor_id = bind_claimed_actor(request, req.actor_id)
    try:
        ticket = get_engine().revoke(
            ticket_id=ticket_id,
            actor_id=actor_id,
            reason=req.reason,
        )
    except GodModeEngineError as exc:
        raise HTTPException(
            status_code=400,
            detail=_god_mode_error_detail("ticket revoke failed", "ticket_revoke_failed"),
        ) from exc
    return {"governed": True, "ticket": ticket.to_json_dict()}


# --- Receipts (audit log) ---------------------------------------------------


@router.get("/api/v1/god-mode/receipts")
def list_receipts(
    actor_id: str | None = None,
    module: str | None = None,
    name: str | None = None,
    outcome: str | None = None,
) -> dict[str, Any]:
    parsed_outcome: GodReceiptOutcome | None = None
    if outcome is not None:
        try:
            parsed_outcome = GodReceiptOutcome(outcome)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=_god_mode_error_detail("invalid outcome", "invalid_outcome"),
            ) from exc
    receipts = get_engine().list_receipts(
        actor_id=actor_id,
        module=module,
        name=name,
        outcome=parsed_outcome,
    )
    return {
        "governed": True,
        "count": len(receipts),
        "receipts": [r.to_json_dict() for r in receipts],
    }
