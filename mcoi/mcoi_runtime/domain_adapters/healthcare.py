"""
Healthcare Domain Adapter.

Translates clinical workflows (assessment, treatment, prescription,
discharge) into the universal causal framework. Distinct shape:

  - Authority chain: licensed clinician + (optional) consult specialist;
    PATIENT_CONSENT is a separate authority-shaped requirement that does
    not slot into the same role hierarchy.
  - Constraints carry contraindication checks, dosage limits, and
    consent presence — each with different violation_response (block /
    escalate / warn).
  - Many actions are structurally irreversible (medication
    administration, surgery, discharge to morgue). REASSESSMENT is the
    primary reversible action.
  - Risk flags surface emergency mode, missing consent, contraindication
    matches, and high-dose alerts.

This adapter intentionally does NOT model diagnosis content or codify
specific drug interactions — it models the governance shape, and leaves
domain-specific rules to the calling system. The acceptance_criteria
list is where domain-specific clinical rules are encoded.
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


class ClinicalActionKind(Enum):
    ASSESSMENT = "assessment"
    DIAGNOSIS = "diagnosis"
    PRESCRIPTION = "prescription"
    PROCEDURE = "procedure"
    SURGERY = "surgery"
    DISCHARGE = "discharge"
    REASSESSMENT = "reassessment"
    REFERRAL = "referral"


@dataclass
class ClinicalRequest:
    kind: ClinicalActionKind
    summary: str
    encounter_id: str
    primary_clinician: str
    consulting_specialists: tuple[str, ...] = ()
    patient_consented: bool = False
    consent_kind: str = ""  # "written" | "verbal" | "implied" | ""
    affected_records: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    contraindication_flags: tuple[str, ...] = ()  # known contraindications
    is_emergency: bool = False
    high_dose: bool = False  # for prescriptions
    blast_radius: str = "encounter"  # encounter | episode | longitudinal | systemic


@dataclass
class ClinicalResult:
    care_protocol: tuple[str, ...]
    required_clinician_signoffs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    consent_recorded: bool
    is_emergency: bool
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


def translate_to_universal(req: ClinicalRequest) -> UniversalRequest:
    if req.consent_kind and req.consent_kind not in {"written", "verbal", "implied"}:
        raise ValueError(
            f"consent_kind {req.consent_kind!r} not in "
            "{'written','verbal','implied'} (or empty)"
        )

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "clinical_state",
        "encounter_id": req.encounter_id,
        "phase": "pre_action",
        "primary_clinician": req.primary_clinician,
        "records": list(req.affected_records),
    }
    target_state = {
        "kind": "clinical_state",
        "encounter_id": req.encounter_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "consent_recorded": req.patient_consented,
    }
    boundary = {
        "inside_predicate": (
            f"encounter_id = {req.encounter_id} ∧ "
            f"records ⊆ {{{', '.join(req.affected_records)}}}"
        ),
        "interface_points": list(req.affected_records),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "clinical_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]

    # Consent constraint.
    # Emergency mode permits implied consent (block lifted to warn);
    # routine action without consent → block.
    consent_violation = "warn" if req.is_emergency else "block"
    if not req.patient_consented:
        constraints.append(
            {
                "domain": "patient_consent",
                "restriction": "patient_consent_recorded_or_emergency",
                "violation_response": consent_violation,
            }
        )

    # Contraindication constraints — each flag becomes an escalation.
    for ci in req.contraindication_flags:
        constraints.append(
            {
                "domain": "contraindication",
                "restriction": f"absence_of:{ci}",
                "violation_response": "escalate",
            }
        )

    # High-dose flag for prescriptions
    if req.high_dose and req.kind == ClinicalActionKind.PRESCRIPTION:
        constraints.append(
            {
                "domain": "dosage",
                "restriction": "high_dose_requires_dual_signoff",
                "violation_response": "escalate",
            }
        )

    # Authority: primary clinician + consulting specialists. Patient
    # consent is recorded separately as an observer requirement.
    authority = (
        f"clinician:{req.primary_clinician}",
    ) + tuple(f"specialist:{s}" for s in req.consulting_specialists)

    observer: tuple[str, ...] = ("medical_record_audit",)
    if req.patient_consented:
        observer = observer + (f"patient_consent:{req.consent_kind or 'unspecified'}",)

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
    original_request: ClinicalRequest,
) -> ClinicalResult:
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

    signoffs = tuple(
        [f"primary: {original_request.primary_clinician}"]
        + [f"specialist: {s}" for s in original_request.consulting_specialists]
    )

    return ClinicalResult(
        care_protocol=protocol,
        required_clinician_signoffs=signoffs,
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        consent_recorded=original_request.patient_consented,
        is_emergency=original_request.is_emergency,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- run_with_ucja ----


def _request_to_ucja_payload(req: ClinicalRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "clinical_action",
    }


def run_with_ucja(
    req: ClinicalRequest,
    *,
    capture: list | None = None,
) -> ClinicalResult:
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
        causation_mechanism="clinical_action",
        causation_strength=0.95,
        transformation_energy=1.0,
        transformation_reversibility=_reversibility_for_kind(req.kind),
        validation_evidence_refs=("ehr_record", "consent_form")
        if req.patient_consented
        else ("ehr_record",),
        validation_confidence=0.95,
        observation_sensor="ehr_observation",
        observation_signal="documented",
        observation_confidence=0.99,
        inference_rule="clinical_guideline",
        inference_certainty=0.9,
        inference_kind="abductive",  # clinical reasoning is best-explanation
        decision_criteria=(
            "clinical_indication_present",
            "patient_consent_or_emergency",
        ),
        decision_justification=(
            f"clinical indication for {req.kind.value} present and "
            f"{'consent recorded' if req.patient_consented else 'emergency mode invoked'}"
        ),
        execution_plan_prefix=f"execute {req.kind.value} for encounter {req.encounter_id}",
        execution_resources=tuple(req.affected_records),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: ClinicalActionKind, summary: str) -> str:
    verb_map = {
        ClinicalActionKind.ASSESSMENT:    "characterize_patient_state",
        ClinicalActionKind.DIAGNOSIS:     "ascribe_pathology_to_observations",
        ClinicalActionKind.PRESCRIPTION:  "issue_pharmaceutical_intervention",
        ClinicalActionKind.PROCEDURE:     "perform_clinical_procedure",
        ClinicalActionKind.SURGERY:       "perform_invasive_intervention",
        ClinicalActionKind.DISCHARGE:     "transition_patient_out_of_care",
        ClinicalActionKind.REASSESSMENT:  "re_characterize_patient_state",
        ClinicalActionKind.REFERRAL:      "transfer_care_to_other_clinician",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "encounter":    "closed",
        "episode":      "selective",
        "longitudinal": "selective",
        "systemic":     "open",
    }.get(blast, "selective")


def _reversibility_for_kind(kind: ClinicalActionKind) -> str:
    if kind in (
        ClinicalActionKind.PRESCRIPTION,
        ClinicalActionKind.PROCEDURE,
        ClinicalActionKind.SURGERY,
        ClinicalActionKind.DISCHARGE,
    ):
        return "irreversible"
    if kind == ClinicalActionKind.REASSESSMENT:
        return "reversible"
    return "unknown"


def _protocol_from_constructs(
    summary: dict[str, int],
    req: ClinicalRequest,
) -> tuple[str, ...]:
    steps: list[str] = []
    if summary.get("observation", 0) > 0:
        steps.append(f"Document initial state of encounter {req.encounter_id}")
    if summary.get("inference", 0) > 0:
        steps.append("Apply clinical guideline to current presentation")
    if summary.get("decision", 0) > 0:
        steps.append("Decide clinical course of action")
    if summary.get("transformation", 0) > 0:
        steps.append(f"Execute {req.kind.value}")
    if req.patient_consented and req.consent_kind:
        steps.append(f"Confirm {req.consent_kind} patient consent on file")
    elif not req.patient_consented and req.is_emergency:
        steps.append("Document emergency-mode implied consent")
    for spec in req.consulting_specialists:
        steps.append(f"Consult specialist: {spec}")
    if summary.get("validation", 0) > 0:
        steps.append("Validate clinical outcome against acceptance criteria")
    if req.kind == ClinicalActionKind.DISCHARGE:
        steps.append("Issue discharge summary and follow-up plan")
    elif req.kind == ClinicalActionKind.SURGERY:
        steps.append("Sign operative note and postoperative orders")
    elif req.kind == ClinicalActionKind.PRESCRIPTION:
        steps.append("Send prescription to pharmacy of record")
    elif req.kind == ClinicalActionKind.REFERRAL:
        steps.append("Transmit clinical summary to receiving clinician")
    if summary.get("execution", 0) > 0:
        steps.append("Persist outcome to medical record")
    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: ClinicalRequest,
) -> tuple[str, ...]:
    flags: list[str] = []
    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")
    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")
    if result.proof_state == "Unknown":
        flags.append("clinical_evidence_insufficient")
    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted")

    if not req.patient_consented and not req.is_emergency:
        flags.append(
            "no_patient_consent_recorded — and not emergency mode"
        )
    if req.is_emergency:
        flags.append(
            "emergency_mode — implied consent invoked; document justification"
        )
    if req.contraindication_flags:
        flags.append(
            f"contraindications_present ({', '.join(req.contraindication_flags)}) — "
            "verify mitigation"
        )
    if req.high_dose and req.kind == ClinicalActionKind.PRESCRIPTION:
        flags.append("high_dose_prescription — dual clinician signoff required")
    if (
        req.kind in (ClinicalActionKind.SURGERY, ClinicalActionKind.PROCEDURE)
        and not req.consulting_specialists
    ):
        flags.append(
            f"{req.kind.value}_without_specialist_consult — review staffing"
        )
    if req.blast_radius == "systemic":
        flags.append("systemic_blast_radius — impacts beyond single encounter")
    if req.kind in (
        ClinicalActionKind.SURGERY,
        ClinicalActionKind.PRESCRIPTION,
        ClinicalActionKind.PROCEDURE,
    ):
        flags.append(
            f"{req.kind.value}_irreversible — confirm before execution"
        )
    return tuple(flags)
