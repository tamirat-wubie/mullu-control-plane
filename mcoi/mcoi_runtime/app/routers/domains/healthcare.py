"""Healthcare domain endpoint."""
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
    ClinicalActionKind,
    ClinicalRequest,
    healthcare_run_with_ucja,
)

router = APIRouter(tags=["domains"])


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


@router.post("/domains/healthcare/process", response_model=DomainOutcome)
def process_healthcare(
    payload: HealthcarePayload,
    persist_run: bool = False,
    auth: MusiaAuthContext = Depends(resolve_musia_auth),
) -> DomainOutcome:
    tenant_id = _resolve_domain_auth(persist_run, auth)
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
    except ValueError as exc:
        raise _domain_error_400("healthcare") from exc
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
