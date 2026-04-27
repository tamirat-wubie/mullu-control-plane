"""
/domains/* — HTTP wrappers for the six concrete domain adapters.

One POST endpoint per domain. Each accepts the domain's request shape as
JSON, runs the full UCJA → SCCCE pipeline, and returns the domain's
result shape.

These endpoints do not require scope `musia.write` even though they
execute cycles, because the UCJA gate fronts every adapter and the
adapter outputs are read-only domain results — no construct registry
state persists from /domains/* calls. Scope is `musia.read` instead.

Auth + tenant resolution flows through `resolve_musia_tenant` like every
other MUSIA route. The tenant is recorded in the result metadata for
audit purposes; per-tenant adapter scoping (separate registries per
tenant) is a future workstream.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.musia_auth import require_read
from mcoi_runtime.app.routers.musia_governance_bridge import gate_domain_run
from mcoi_runtime.substrate.registry_store import STORE
from mcoi_runtime.domain_adapters import (
    BusinessActionKind,
    BusinessRequest,
    ClinicalActionKind,
    ClinicalRequest,
    EducationActionKind,
    EducationRequest,
    ManufacturingActionKind,
    ManufacturingRequest,
    ResearchActionKind,
    ResearchRequest,
    SoftwareRequest,
    SoftwareWorkKind,
    business_run_with_ucja,
    education_run_with_ucja,
    healthcare_run_with_ucja,
    manufacturing_run_with_ucja,
    research_run_with_ucja,
    software_run_with_ucja,
)


router = APIRouter(prefix="/domains", tags=["domains"])


# ---- Shared response shape ----


class DomainOutcome(BaseModel):
    """Common envelope returned by every /domains/* endpoint."""

    domain: str
    governance_status: str
    audit_trail_id: str
    risk_flags: list[str]
    plan: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str
    run_id: str | None = None  # populated when persist_run=true and merge succeeds


def _gate_or_blocked_outcome(
    *,
    domain: str,
    tenant_id: str,
    summary: str,
) -> DomainOutcome | None:
    """Run the domain-level chain gate. Returns None on pass, a blocked
    DomainOutcome on rejection. The caller short-circuits when this
    returns non-None, skipping the cycle entirely.

    v4.16.0+. The audit_trail_id is a fresh UUID identifying this gate
    decision so operators correlating chain logs with domain responses
    have a stable handle.
    """
    ok, reason = gate_domain_run(
        domain=domain,
        tenant_id=tenant_id,
        summary=summary,
    )
    if ok:
        return None
    return DomainOutcome(
        domain=domain,
        governance_status=f"blocked: chain_rejected ({reason})",
        audit_trail_id=str(uuid4()),
        risk_flags=[f"chain_gate_rejected: {reason}"],
        plan=[],
        metadata={"chain_gate": "rejected", "reason": reason},
        tenant_id=tenant_id,
        run_id=None,
    )


def _maybe_persist_run(
    tenant_id: str,
    persist_run: bool,
    captured: list,
    risk_flags: list[str],
    *,
    domain: str | None = None,
    summary: str | None = None,
) -> str | None:
    """If persist_run is set, merge captured constructs into the tenant registry.

    v4.12.0: ``domain`` and ``summary`` are stamped on each construct's
    metadata as ``run_domain`` / ``run_summary``, joining ``run_id`` and
    ``run_timestamp``. This makes a persisted run self-describing without
    requiring the caller to query the registry by run_id and reconstruct.

    Returns the run_id when merge succeeds. On quota rejection, appends
    a risk flag to risk_flags (mutates) and returns None — the cycle
    result is still returned to the caller, just without persistence.
    """
    if not persist_run or not captured:
        return None
    state = STORE.get_or_create(tenant_id)
    run_id = f"run-{uuid4().hex[:12]}"
    ok, reason = state.merge_run(
        run_id,
        captured,
        domain=domain,
        summary=summary,
    )
    if not ok:
        risk_flags.append(f"persist_run_rejected: {reason}")
        return None
    return run_id


# ---- software_dev ----


class SoftwareDevPayload(BaseModel):
    kind: str  # one of SoftwareWorkKind values
    summary: str
    repository: str
    target_branch: str = "main"
    affected_files: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    blast_radius: str = "module"
    reviewer_required: bool = True


def _kind_or_400(enum_cls, value: str):
    try:
        return enum_cls(value)
    except ValueError:
        valid = ", ".join(e.value for e in enum_cls)
        raise HTTPException(
            status_code=400,
            detail=f"unknown kind {value!r}; valid: {valid}",
        )


@router.post("/software-dev/process", response_model=DomainOutcome)
def process_software_dev(
    payload: SoftwareDevPayload,
    persist_run: bool = False,
    tenant_id: str = Depends(require_read),
) -> DomainOutcome:
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


# ---- business_process ----


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


@router.post("/business-process/process", response_model=DomainOutcome)
def process_business(
    payload: BusinessPayload,
    persist_run: bool = False,
    tenant_id: str = Depends(require_read),
) -> DomainOutcome:
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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


# ---- scientific_research ----


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


@router.post("/scientific-research/process", response_model=DomainOutcome)
def process_research(
    payload: ResearchPayload,
    persist_run: bool = False,
    tenant_id: str = Depends(require_read),
) -> DomainOutcome:
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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


# ---- manufacturing ----


class ManufacturingPayload(BaseModel):
    kind: str
    summary: str
    line_id: str
    operator_id: str
    quality_engineer: str = ""
    iso_certifications: list[str] = Field(default_factory=list)
    affected_part_numbers: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    tolerance_microns: float | None = None
    expected_yield_pct: float = 0.95
    safety_critical: bool = False
    blast_radius: str = "line"


@router.post("/manufacturing/process", response_model=DomainOutcome)
def process_manufacturing(
    payload: ManufacturingPayload,
    persist_run: bool = False,
    tenant_id: str = Depends(require_read),
) -> DomainOutcome:
    blocked = _gate_or_blocked_outcome(
        domain="manufacturing", tenant_id=tenant_id, summary=payload.summary,
    )
    if blocked is not None:
        return blocked
    kind = _kind_or_400(ManufacturingActionKind, payload.kind)
    try:
        req = ManufacturingRequest(
            kind=kind,
            summary=payload.summary,
            line_id=payload.line_id,
            operator_id=payload.operator_id,
            quality_engineer=payload.quality_engineer,
            iso_certifications=tuple(payload.iso_certifications),
            affected_part_numbers=tuple(payload.affected_part_numbers),
            acceptance_criteria=tuple(payload.acceptance_criteria),
            tolerance_microns=payload.tolerance_microns,
            expected_yield_pct=payload.expected_yield_pct,
            safety_critical=payload.safety_critical,
            blast_radius=payload.blast_radius,
        )
        captured: list = [] if persist_run else None
        out = manufacturing_run_with_ucja(req, capture=captured)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    risk_flags = list(out.risk_flags)
    run_id = _maybe_persist_run(
        tenant_id, persist_run, captured or [], risk_flags,
        domain="manufacturing", summary=payload.summary,
    )
    return DomainOutcome(
        domain="manufacturing",
        governance_status=out.governance_status,
        audit_trail_id=str(out.audit_trail_id),
        risk_flags=risk_flags,
        plan=list(out.production_protocol),
        metadata={
            "required_signoffs": list(out.required_signoffs),
            "estimated_blast_radius": out.estimated_blast_radius,
            "tolerance_microns": out.tolerance_microns,
            "expected_yield_pct": out.expected_yield_pct,
        },
        tenant_id=tenant_id,
        run_id=run_id,
    )


# ---- healthcare ----


class HealthcarePayload(BaseModel):
    kind: str
    summary: str
    encounter_id: str
    primary_clinician: str
    consulting_specialists: list[str] = Field(default_factory=list)
    patient_consented: bool = False
    consent_kind: str = ""
    affected_records: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    contraindication_flags: list[str] = Field(default_factory=list)
    is_emergency: bool = False
    high_dose: bool = False
    blast_radius: str = "encounter"


@router.post("/healthcare/process", response_model=DomainOutcome)
def process_healthcare(
    payload: HealthcarePayload,
    persist_run: bool = False,
    tenant_id: str = Depends(require_read),
) -> DomainOutcome:
    blocked = _gate_or_blocked_outcome(
        domain="healthcare", tenant_id=tenant_id, summary=payload.summary,
    )
    if blocked is not None:
        return blocked
    kind = _kind_or_400(ClinicalActionKind, payload.kind)
    try:
        req = ClinicalRequest(
            kind=kind,
            summary=payload.summary,
            encounter_id=payload.encounter_id,
            primary_clinician=payload.primary_clinician,
            consulting_specialists=tuple(payload.consulting_specialists),
            patient_consented=payload.patient_consented,
            consent_kind=payload.consent_kind,
            affected_records=tuple(payload.affected_records),
            acceptance_criteria=tuple(payload.acceptance_criteria),
            contraindication_flags=tuple(payload.contraindication_flags),
            is_emergency=payload.is_emergency,
            high_dose=payload.high_dose,
            blast_radius=payload.blast_radius,
        )
        captured: list = [] if persist_run else None
        out = healthcare_run_with_ucja(req, capture=captured)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    risk_flags = list(out.risk_flags)
    run_id = _maybe_persist_run(
        tenant_id, persist_run, captured or [], risk_flags,
        domain="healthcare", summary=payload.summary,
    )
    return DomainOutcome(
        domain="healthcare",
        governance_status=out.governance_status,
        audit_trail_id=str(out.audit_trail_id),
        risk_flags=risk_flags,
        plan=list(out.care_protocol),
        metadata={
            "required_clinician_signoffs": list(out.required_clinician_signoffs),
            "estimated_blast_radius": out.estimated_blast_radius,
            "consent_recorded": out.consent_recorded,
            "is_emergency": out.is_emergency,
        },
        tenant_id=tenant_id,
        run_id=run_id,
    )


# ---- education ----


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


@router.post("/education/process", response_model=DomainOutcome)
def process_education(
    payload: EducationPayload,
    persist_run: bool = False,
    tenant_id: str = Depends(require_read),
) -> DomainOutcome:
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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


# ---- Index ----


@router.get("", response_model=list[str])
def list_domains() -> list[str]:
    """List the six available domain adapters."""
    return [
        "software_dev",
        "business_process",
        "scientific_research",
        "manufacturing",
        "healthcare",
        "education",
    ]
