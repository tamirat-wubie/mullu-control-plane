"""Manufacturing domain endpoint."""
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
    ManufacturingActionKind,
    ManufacturingRequest,
    manufacturing_run_with_ucja,
)

router = APIRouter(tags=["domains"])


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


@router.post("/domains/manufacturing/process", response_model=DomainOutcome)
def process_manufacturing(
    payload: ManufacturingPayload,
    persist_run: bool = False,
    auth: MusiaAuthContext = Depends(resolve_musia_auth),
) -> DomainOutcome:
    tenant_id = _resolve_domain_auth(persist_run, auth)
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
    except ValueError as exc:
        raise _domain_error_400("manufacturing") from exc
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
