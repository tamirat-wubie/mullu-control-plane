"""Scientific research domain endpoint."""
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
    ResearchActionKind,
    ResearchRequest,
    research_run_with_ucja,
)

router = APIRouter(tags=["domains"])


class ResearchPayload(BaseModel):
    kind: str
    summary: str
    study_id: str
    principal_investigator: str
    peer_reviewers: list[str] = Field(default_factory=list)
    affected_corpus: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    confidence_threshold: float = 0.95
    minimum_replications: int = 1
    statistical_power_target: float = 0.8
    blast_radius: str = "study"


@router.post("/domains/scientific-research/process", response_model=DomainOutcome)
def process_research(
    payload: ResearchPayload,
    persist_run: bool = False,
    auth: MusiaAuthContext = Depends(resolve_musia_auth),
) -> DomainOutcome:
    tenant_id = _resolve_domain_auth(persist_run, auth)
    blocked = _gate_or_blocked_outcome(
        domain="scientific_research", tenant_id=tenant_id, summary=payload.summary,
    )
    if blocked is not None:
        return blocked
    kind = _kind_or_400(ResearchActionKind, payload.kind)
    try:
        req = ResearchRequest(
            kind=kind,
            summary=payload.summary,
            study_id=payload.study_id,
            principal_investigator=payload.principal_investigator,
            peer_reviewers=tuple(payload.peer_reviewers),
            affected_corpus=tuple(payload.affected_corpus),
            acceptance_criteria=tuple(payload.acceptance_criteria),
            confidence_threshold=payload.confidence_threshold,
            minimum_replications=payload.minimum_replications,
            statistical_power_target=payload.statistical_power_target,
            blast_radius=payload.blast_radius,
        )
        captured: list = [] if persist_run else None
        out = research_run_with_ucja(req, capture=captured)
    except ValueError as exc:
        raise _domain_error_400("scientific_research") from exc
    risk_flags = list(out.risk_flags)
    run_id = _maybe_persist_run(
        tenant_id, persist_run, captured or [], risk_flags,
        domain="scientific_research", summary=payload.summary,
    )
    return DomainOutcome(
        domain="scientific_research",
        governance_status=out.governance_status,
        audit_trail_id=str(out.audit_trail_id),
        risk_flags=risk_flags,
        plan=list(out.research_protocol),
        metadata={
            "required_reviewers": list(out.required_reviewers),
            "estimated_blast_radius": out.estimated_blast_radius,
            "confidence_threshold": out.confidence_threshold,
            "minimum_replications": out.minimum_replications,
        },
        tenant_id=tenant_id,
        run_id=run_id,
    )
