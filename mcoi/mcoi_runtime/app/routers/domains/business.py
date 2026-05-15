"""Business process domain endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.domains._common import (
    DomainOutcome,
    _domain_error_400,
    _gate_or_blocked_outcome,
    _kind_or_400,
    _maybe_persist_run,
    _resolve_domain_auth,
)
from mcoi_runtime.app.routers.musia_auth import MusiaAuthContext, resolve_musia_auth
from mcoi_runtime.domain_adapters import (
    BusinessActionKind,
    BusinessRequest,
    business_run_with_ucja,
)

router = APIRouter(tags=["domains"])


class BusinessPayload(BaseModel):
    kind: str
    summary: str
    process_id: str
    initiator: str
    approval_chain: list[str] = Field(default_factory=list)
    sla_deadline_hours: float | None = None
    affected_systems: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    dollar_impact: float = 0.0
    blast_radius: str = "department"


@router.post("/domains/business-process/process", response_model=DomainOutcome)
def process_business(
    payload: BusinessPayload,
    persist_run: bool = False,
    auth: MusiaAuthContext = Depends(resolve_musia_auth),
) -> DomainOutcome:
    tenant_id = _resolve_domain_auth(persist_run, auth)
    blocked = _gate_or_blocked_outcome(
        domain="business_process", tenant_id=tenant_id, summary=payload.summary,
    )
    if blocked is not None:
        return blocked
    kind = _kind_or_400(BusinessActionKind, payload.kind)
    try:
        req = BusinessRequest(
            kind=kind,
            summary=payload.summary,
            process_id=payload.process_id,
            initiator=payload.initiator,
            approval_chain=tuple(payload.approval_chain),
            sla_deadline_hours=payload.sla_deadline_hours,
            affected_systems=tuple(payload.affected_systems),
            acceptance_criteria=tuple(payload.acceptance_criteria),
            dollar_impact=payload.dollar_impact,
            blast_radius=payload.blast_radius,
        )
        captured: list = [] if persist_run else None
        out = business_run_with_ucja(req, capture=captured)
    except ValueError as exc:
        raise _domain_error_400("business_process") from exc
    risk_flags = list(out.risk_flags)
    run_id = _maybe_persist_run(
        tenant_id, persist_run, captured or [], risk_flags,
        domain="business_process", summary=payload.summary,
    )
    return DomainOutcome(
        domain="business_process",
        governance_status=out.governance_status,
        audit_trail_id=str(out.audit_trail_id),
        risk_flags=risk_flags,
        plan=list(out.workflow_steps),
        metadata={
            "required_approvals": list(out.required_approvals),
            "estimated_blast_radius": out.estimated_blast_radius,
            "sla_deadline_hours": out.sla_deadline_hours,
        },
        tenant_id=tenant_id,
        run_id=run_id,
    )
