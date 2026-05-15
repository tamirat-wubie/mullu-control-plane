"""Education domain endpoint."""
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
    EducationActionKind,
    EducationRequest,
    education_run_with_ucja,
)

router = APIRouter(tags=["domains"])


class EducationPayload(BaseModel):
    kind: str
    summary: str
    course_id: str
    instructor: str
    curriculum_committee: list[str] = Field(default_factory=list)
    accreditation_body: str = ""
    affected_learners: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    prerequisite_courses: list[str] = Field(default_factory=list)
    accessibility_requirements: list[str] = Field(default_factory=list)
    blast_radius: str = "course"


@router.post("/domains/education/process", response_model=DomainOutcome)
def process_education(
    payload: EducationPayload,
    persist_run: bool = False,
    auth: MusiaAuthContext = Depends(resolve_musia_auth),
) -> DomainOutcome:
    tenant_id = _resolve_domain_auth(persist_run, auth)
    blocked = _gate_or_blocked_outcome(
        domain="education", tenant_id=tenant_id, summary=payload.summary,
    )
    if blocked is not None:
        return blocked
    kind = _kind_or_400(EducationActionKind, payload.kind)
    try:
        req = EducationRequest(
            kind=kind,
            summary=payload.summary,
            course_id=payload.course_id,
            instructor=payload.instructor,
            curriculum_committee=tuple(payload.curriculum_committee),
            accreditation_body=payload.accreditation_body,
            affected_learners=tuple(payload.affected_learners),
            learning_objectives=tuple(payload.learning_objectives),
            acceptance_criteria=tuple(payload.acceptance_criteria),
            prerequisite_courses=tuple(payload.prerequisite_courses),
            accessibility_requirements=tuple(payload.accessibility_requirements),
            blast_radius=payload.blast_radius,
        )
        captured: list = [] if persist_run else None
        out = education_run_with_ucja(req, capture=captured)
    except ValueError as exc:
        raise _domain_error_400("education") from exc
    risk_flags = list(out.risk_flags)
    run_id = _maybe_persist_run(
        tenant_id, persist_run, captured or [], risk_flags,
        domain="education", summary=payload.summary,
    )
    return DomainOutcome(
        domain="education",
        governance_status=out.governance_status,
        audit_trail_id=str(out.audit_trail_id),
        risk_flags=risk_flags,
        plan=list(out.instructional_protocol),
        metadata={
            "required_signoffs": list(out.required_signoffs),
            "estimated_blast_radius": out.estimated_blast_radius,
            "learning_objectives": list(out.learning_objectives),
        },
        tenant_id=tenant_id,
        run_id=run_id,
    )
