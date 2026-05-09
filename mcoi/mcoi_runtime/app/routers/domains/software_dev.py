"""Software development domain endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.domains._common import (
    DomainOutcome,
    _gate_or_blocked_outcome,
    _kind_or_400,
    _maybe_persist_run,
    _resolve_domain_auth,
)
from mcoi_runtime.app.routers.musia_auth import MusiaAuthContext, resolve_musia_auth
from mcoi_runtime.domain_adapters import (
    SoftwareRequest,
    SoftwareWorkKind,
    software_run_with_ucja,
)

router = APIRouter(tags=["domains"])


class SoftwareDevPayload(BaseModel):
    kind: str  # one of SoftwareWorkKind values
    summary: str
    repository: str
    target_branch: str = "main"
    affected_files: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    blast_radius: str = "module"
    reviewer_required: bool = True


@router.post("/domains/software-dev/process", response_model=DomainOutcome)
def process_software_dev(
    payload: SoftwareDevPayload,
    persist_run: bool = False,
    auth: MusiaAuthContext = Depends(resolve_musia_auth),
) -> DomainOutcome:
    tenant_id = _resolve_domain_auth(persist_run, auth)
    blocked = _gate_or_blocked_outcome(
        domain="software_dev", tenant_id=tenant_id, summary=payload.summary,
    )
    if blocked is not None:
        return blocked
    kind = _kind_or_400(SoftwareWorkKind, payload.kind)
    req = SoftwareRequest(
        kind=kind,
        summary=payload.summary,
        repository=payload.repository,
        target_branch=payload.target_branch,
        affected_files=tuple(payload.affected_files),
        acceptance_criteria=tuple(payload.acceptance_criteria),
        blast_radius=payload.blast_radius,
        reviewer_required=payload.reviewer_required,
    )
    captured: list = [] if persist_run else None
    out = software_run_with_ucja(req, capture=captured)
    risk_flags = list(out.risk_flags)
    run_id = _maybe_persist_run(
        tenant_id, persist_run, captured or [], risk_flags,
        domain="software_dev", summary=payload.summary,
    )
    return DomainOutcome(
        domain="software_dev",
        governance_status=out.governance_status,
        audit_trail_id=str(out.audit_trail_id),
        risk_flags=risk_flags,
        plan=list(out.work_plan),
        metadata={
            "required_reviewers": list(out.required_reviewers),
            "estimated_blast_radius": out.estimated_blast_radius,
            "completion_criteria": list(out.completion_criteria),
        },
        tenant_id=tenant_id,
        run_id=run_id,
    )
