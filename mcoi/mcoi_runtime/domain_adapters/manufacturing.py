"""
Manufacturing Domain Adapter.

Translates production-line workflows (machining, assembly, QC, recall)
into the universal causal framework. Distinct shape vs prior adapters:

  - Authority comes from quality engineers + ISO certifications, not
    individual reviewers.
  - Constraints carry numerical tolerances (dimensional, surface finish)
    and yield thresholds — escalate violations rather than block.
  - Most actions are forward-only (parts consumed, surfaces machined).
    Only `REWORK` is reversibility="reversible". `RECALL` is
    irreversible at the framework level (the recall event is recorded;
    the recalled units already shipped).
  - Risk flags surface tight-tolerance + low-yield combinations and
    safety-critical category status.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from mcoi_runtime.domain_adapters._cycle_helpers import (
    StepOverrides,
    run_default_cycle,
)
from mcoi_runtime.domain_adapters.software_dev import (
    UniversalRequest,
    UniversalResult,
)


class ManufacturingActionKind(Enum):
    MACHINING = "machining"
    ASSEMBLY = "assembly"
    QUALITY_INSPECTION = "quality_inspection"
    REWORK = "rework"
    SCRAP = "scrap"
    RECALL = "recall"
    CALIBRATION = "calibration"
    BATCH_RELEASE = "batch_release"


@dataclass
class ManufacturingRequest:
    kind: ManufacturingActionKind
    summary: str
    line_id: str
    operator_id: str
    quality_engineer: str = ""
    iso_certifications: tuple[str, ...] = ()
    affected_part_numbers: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    tolerance_microns: float | None = None  # tightest dimensional tolerance
    expected_yield_pct: float = 0.95  # batch yield target [0,1]
    safety_critical: bool = False
    blast_radius: str = "line"  # station | line | plant | enterprise


@dataclass
class ManufacturingResult:
    production_protocol: tuple[str, ...]
    required_signoffs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    tolerance_microns: float | None
    expected_yield_pct: float
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


def translate_to_universal(req: ManufacturingRequest) -> UniversalRequest:
    if req.tolerance_microns is not None and req.tolerance_microns < 0:
        raise ValueError("tolerance_microns must be non-negative when set")
    if not (0.0 <= req.expected_yield_pct <= 1.0):
        raise ValueError("expected_yield_pct must be in [0,1]")

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "production_state",
        "line_id": req.line_id,
        "phase": "pre_action",
        "operator_id": req.operator_id,
        "part_numbers": list(req.affected_part_numbers),
    }
    target_state = {
        "kind": "production_state",
        "line_id": req.line_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "expected_yield_pct": req.expected_yield_pct,
    }
    boundary = {
        "inside_predicate": (
            f"line_id = {req.line_id} ∧ "
            f"parts ⊆ {{{', '.join(req.affected_part_numbers)}}}"
        ),
        "interface_points": list(req.affected_part_numbers),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "production_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]
    if req.tolerance_microns is not None:
        constraints.append(
            {
                "domain": "dimensional_tolerance",
                "restriction": f"deviation_microns <= {req.tolerance_microns}",
                "violation_response": "escalate",
            }
        )
    constraints.append(
        {
            "domain": "yield",
            "restriction": f"batch_yield >= {req.expected_yield_pct}",
            "violation_response": "warn",
        }
    )
    if req.safety_critical:
        constraints.append(
            {
                "domain": "safety",
                "restriction": "safety_critical_category_validated",
                "violation_response": "block",
            }
        )

    # Authority: QE if present, otherwise operator. ISO certs become observers.
    if req.quality_engineer:
        authority = (
            f"quality_engineer:{req.quality_engineer}",
            f"operator:{req.operator_id}",
        )
    else:
        authority = (f"operator:{req.operator_id}",)
    observer = tuple(f"iso:{c}" for c in req.iso_certifications) or ("line_audit_log",)

    return UniversalRequest(
        purpose_statement=purpose,
        initial_state_descriptor=initial_state,
        target_state_descriptor=target_state,
        boundary_specification=boundary,
        constraint_set=tuple(constraints),
        authority_required=authority,
        observer_required=observer,
    )


def translate_from_universal(
    universal_result: UniversalResult,
    original_request: ManufacturingRequest,
) -> ManufacturingResult:
    protocol = _protocol_from_constructs(
        universal_result.construct_graph_summary,
        original_request,
    )
    risk_flags = _risk_flags_from_result(universal_result, original_request)
    governance_status = (
        "approved"
        if universal_result.proof_state == "Pass"
        else f"blocked: {universal_result.proof_state}"
    )

    signoffs: list[str] = []
    if original_request.quality_engineer:
        signoffs.append(f"QE: {original_request.quality_engineer}")
    if original_request.iso_certifications:
        signoffs.extend(f"ISO: {c}" for c in original_request.iso_certifications)

    return ManufacturingResult(
        production_protocol=protocol,
        required_signoffs=tuple(signoffs),
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        tolerance_microns=original_request.tolerance_microns,
        expected_yield_pct=original_request.expected_yield_pct,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- run_with_ucja ----


def _request_to_ucja_payload(req: ManufacturingRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "production_action",
    }


def run_with_ucja(
    req: ManufacturingRequest,
    *,
    capture: list | None = None,
) -> ManufacturingResult:
    from mcoi_runtime.ucja import UCJAPipeline

    payload = _request_to_ucja_payload(req)
    outcome = UCJAPipeline().run(payload)

    if not outcome.accepted:
        proof_state = "Fail" if outcome.rejected else "Unknown"
        rejected = (
            {"layer": outcome.halted_at_layer, "reason": outcome.reason},
        )
        universal_result = UniversalResult(
            job_definition_id=outcome.draft.job_id,
            construct_graph_summary={},
            cognitive_cycles_run=0,
            converged=False,
            proof_state=proof_state,
            rejected_deltas=rejected,
        )
        return translate_from_universal(universal_result, req)

    universal_req = translate_to_universal(req)
    overrides = StepOverrides(
        causation_mechanism="production_action",
        causation_strength=req.expected_yield_pct,
        transformation_energy=float(len(req.affected_part_numbers) or 1),
        transformation_reversibility=_reversibility_for_kind(req.kind),
        validation_evidence_refs=("qc_inspection_pass",),
        validation_confidence=req.expected_yield_pct,
        observation_sensor="line_inspection_camera",
        observation_signal="in_spec",
        observation_confidence=0.99,
        inference_rule="control_chart",
        inference_certainty=req.expected_yield_pct,
        inference_kind="inductive",
        decision_criteria=("acceptance_criteria_met", "iso_compliance_verified"),
        decision_justification=(
            f"QC passed with yield ≥ {req.expected_yield_pct:.2f}"
        ),
        execution_plan_prefix=f"execute {req.kind.value} on line {req.line_id}",
        execution_resources=tuple(req.affected_part_numbers),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: ManufacturingActionKind, summary: str) -> str:
    verb_map = {
        ManufacturingActionKind.MACHINING:          "remove_material_to_specification",
        ManufacturingActionKind.ASSEMBLY:           "join_components_into_unit",
        ManufacturingActionKind.QUALITY_INSPECTION: "verify_against_specification",
        ManufacturingActionKind.REWORK:             "correct_nonconforming_unit",
        ManufacturingActionKind.SCRAP:              "discard_unrecoverable_unit",
        ManufacturingActionKind.RECALL:             "withdraw_shipped_units_from_field",
        ManufacturingActionKind.CALIBRATION:        "align_instrument_to_reference",
        ManufacturingActionKind.BATCH_RELEASE:      "approve_batch_for_shipment",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "station":    "closed",
        "line":       "selective",
        "plant":      "selective",
        "enterprise": "open",
    }.get(blast, "selective")


def _reversibility_for_kind(kind: ManufacturingActionKind) -> str:
    if kind == ManufacturingActionKind.REWORK:
        return "reversible"
    if kind in (
        ManufacturingActionKind.MACHINING,
        ManufacturingActionKind.ASSEMBLY,
        ManufacturingActionKind.SCRAP,
        ManufacturingActionKind.RECALL,
    ):
        return "irreversible"
    return "unknown"


def _protocol_from_constructs(
    summary: dict[str, int],
    req: ManufacturingRequest,
) -> tuple[str, ...]:
    steps: list[str] = []
    if summary.get("observation", 0) > 0:
        steps.append(f"Capture initial state of line {req.line_id}")
    if summary.get("inference", 0) > 0:
        steps.append("Apply control-chart inference to current run")
    if summary.get("decision", 0) > 0:
        steps.append("Decide accept/rework/scrap per acceptance criteria")
    if summary.get("transformation", 0) > 0:
        steps.append(
            f"Execute {req.kind.value} on {len(req.affected_part_numbers)} part(s)"
        )
    if req.quality_engineer:
        steps.append(f"Route to quality engineer: {req.quality_engineer}")
    for cert in req.iso_certifications:
        steps.append(f"Verify ISO {cert} compliance")
    if summary.get("validation", 0) > 0:
        steps.append("Inspect outcome against acceptance criteria")
    if req.kind == ManufacturingActionKind.RECALL:
        steps.append("Notify field service and customers of recall scope")
    elif req.kind == ManufacturingActionKind.BATCH_RELEASE:
        steps.append("Issue release certificate and ship")
    elif req.kind == ManufacturingActionKind.CALIBRATION:
        steps.append("Record calibration in instrument history")
    if summary.get("execution", 0) > 0:
        steps.append("Persist outcome to line audit log")
    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: ManufacturingRequest,
) -> tuple[str, ...]:
    flags: list[str] = []
    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")
    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")
    if result.proof_state == "Unknown":
        flags.append("inspection_evidence_insufficient")
    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted")
    if req.tolerance_microns is not None and req.tolerance_microns <= 5.0:
        flags.append(
            f"tight_tolerance ({req.tolerance_microns}μm) — verify gauge R&R"
        )
    if req.expected_yield_pct < 0.9:
        flags.append(
            f"low_yield_target ({req.expected_yield_pct:.2f}) — review process capability"
        )
    if (
        req.tolerance_microns is not None
        and req.tolerance_microns <= 5.0
        and req.expected_yield_pct < 0.95
    ):
        flags.append(
            "tight_tolerance_low_yield — production capability mismatch likely"
        )
    if req.safety_critical:
        flags.append(
            "safety_critical — recall path must be pre-armed"
        )
    if req.blast_radius == "enterprise":
        flags.append("enterprise_blast_radius — coordinate with corporate quality")
    if req.kind == ManufacturingActionKind.RECALL:
        flags.append("recall — notify regulators per applicable jurisdiction")
    if req.kind == ManufacturingActionKind.BATCH_RELEASE and not req.quality_engineer:
        flags.append(
            "batch_release_without_qe — release without quality engineer signoff"
        )
    return tuple(flags)
