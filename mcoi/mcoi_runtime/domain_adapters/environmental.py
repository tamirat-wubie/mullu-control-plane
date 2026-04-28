"""
Environmental / ESG Domain Adapter.

Translates environmental and sustainability actions (emissions
reporting, permit compliance check, audit, remediation plan,
remediation execution, environmental incident response, disclosure
filing, carbon offset purchase, impact assessment, consent decree
action) into the universal causal framework. Distinct shape:

  - Authority chain: responsible EHS officer + reviewer chain
    (internal audit, sustainability lead). Regulators (EPA-equivalent),
    third-party verifiers, and affected communities are observer-
    shaped — they witness but do not authorize. Third-party
    verification is recorded as an observer on every action because
    ESG governance demands independent attestation.
  - Constraints carry acceptance criteria, current-exceedance flags,
    environmental-justice review, and regulatory-regime presence —
    each with different violation_response. Active exceedance blocks
    routine action UNLESS a declared incident emergency relaxes it
    to escalate (response actions can proceed during exceedance to
    bring the system back into compliance).
  - Many actions are irreversible once filed/done (disclosure_filing,
    consent_decree_action, carbon_offset_purchase,
    remediation_execution). Plans, audits, assessments, and routine
    monitoring remain reversible.
  - Risk flags surface active exceedance, environmental-justice
    concerns, missing third-party verification on disclosure,
    regional / cross-media blast radius, and irreversible commits.

This adapter intentionally does NOT model emissions accounting or
specific regulatory thresholds — it models the governance shape, and
leaves jurisdiction-specific rules (CAA, CWA, GHGRP, CDP, TCFD,
SFDR, EU CSRD, SEC climate disclosure) to the calling system.
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


class EnvironmentalActionKind(Enum):
    EMISSIONS_REPORTING = "emissions_reporting"
    PERMIT_COMPLIANCE_CHECK = "permit_compliance_check"
    AUDIT = "audit"
    REMEDIATION_PLAN = "remediation_plan"
    REMEDIATION_EXECUTION = "remediation_execution"
    INCIDENT_RESPONSE = "incident_response"  # spill, leak, acute release
    DISCLOSURE_FILING = "disclosure_filing"
    CARBON_OFFSET_PURCHASE = "carbon_offset_purchase"
    IMPACT_ASSESSMENT = "impact_assessment"
    CONSENT_DECREE_ACTION = "consent_decree_action"


_VALID_MEDIA = frozenset({"air", "water", "soil", "biota"})


@dataclass
class EnvironmentalRequest:
    kind: EnvironmentalActionKind
    summary: str
    facility_id: str
    responsible_officer: str  # EHS officer / sustainability lead
    reviewer_chain: tuple[str, ...] = ()
    operator: str = ""  # operating entity
    regulatory_authority: str = ""  # e.g. "EPA", "CARB", "EU-ETS"
    regulatory_regime: tuple[str, ...] = ()  # e.g. ("CAA","CDP","TCFD")
    jurisdiction: str = ""
    affected_media: tuple[str, ...] = ()  # subset of {air,water,soil,biota}
    affected_communities: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    exceedance_present: bool = False  # current exceedance of permit/limit
    environmental_justice_concern: bool = False
    third_party_verified: bool = False
    is_emergency: bool = False  # acute release / spill / declared incident
    blast_radius: str = "facility"  # facility | watershed | airshed | regional


@dataclass
class EnvironmentalResult:
    stewardship_protocol: tuple[str, ...]
    required_signoffs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    third_party_verified: bool
    is_emergency: bool
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


_RESPONSE_KINDS = (
    EnvironmentalActionKind.INCIDENT_RESPONSE,
    EnvironmentalActionKind.REMEDIATION_EXECUTION,
)


def translate_to_universal(req: EnvironmentalRequest) -> UniversalRequest:
    bad_media = [m for m in req.affected_media if m not in _VALID_MEDIA]
    if bad_media:
        raise ValueError(
            f"unknown environmental media {bad_media!r}; valid: "
            f"{sorted(_VALID_MEDIA)}"
        )
    if (
        req.kind == EnvironmentalActionKind.DISCLOSURE_FILING
        and not req.regulatory_regime
    ):
        raise ValueError(
            f"disclosure_filing requires regulatory_regime "
            f"(facility_id={req.facility_id})"
        )

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "environmental_state",
        "facility_id": req.facility_id,
        "phase": "pre_action",
        "responsible_officer": req.responsible_officer,
        "operator": req.operator,
        "media": list(req.affected_media),
    }
    target_state = {
        "kind": "environmental_state",
        "facility_id": req.facility_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "third_party_verified": req.third_party_verified,
    }
    boundary = {
        "inside_predicate": (
            f"facility_id = {req.facility_id} ∧ "
            f"media ⊆ {{{', '.join(req.affected_media)}}}"
        ),
        "interface_points": list(req.affected_media),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "environmental_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]

    # Active exceedance — blocks routine actions UNLESS emergency
    # response (INCIDENT_RESPONSE / REMEDIATION_EXECUTION) where the
    # whole point is to act during exceedance to restore compliance.
    if req.exceedance_present and req.kind not in _RESPONSE_KINDS:
        ex_response = "escalate" if req.is_emergency else "block"
        constraints.append(
            {
                "domain": "exceedance",
                "restriction": "no_routine_action_during_exceedance",
                "violation_response": ex_response,
            }
        )

    # Environmental justice — heightened review for actions
    # affecting protected populations. Always escalates; emergency
    # does not relax (EJ concerns persist through emergency response).
    if req.environmental_justice_concern:
        constraints.append(
            {
                "domain": "environmental_justice",
                "restriction": "ej_review_completed",
                "violation_response": "escalate",
            }
        )

    # Disclosure filings require third-party verification — block
    # without it, since assured data is the entire value of the
    # filing under TCFD/CDP/SFDR/CSRD/SEC regimes.
    if (
        req.kind == EnvironmentalActionKind.DISCLOSURE_FILING
        and not req.third_party_verified
    ):
        constraints.append(
            {
                "domain": "verification",
                "restriction": "third_party_verification_complete",
                "violation_response": "block",
            }
        )

    authority = (
        f"officer:{req.responsible_officer}",
    ) + tuple(f"reviewer:{r}" for r in req.reviewer_chain)

    observer: tuple[str, ...] = ("ehs_audit",)
    if req.regulatory_authority:
        observer = observer + (f"regulator:{req.regulatory_authority}",)
    for regime in req.regulatory_regime:
        observer = observer + (f"regime:{regime}",)
    if req.jurisdiction:
        observer = observer + (f"jurisdiction:{req.jurisdiction}",)
    if req.operator:
        observer = observer + (f"operator:{req.operator}",)
    for community in req.affected_communities:
        observer = observer + (f"community:{community}",)
    if req.environmental_justice_concern:
        observer = observer + ("ej_oversight",)
    if req.third_party_verified:
        observer = observer + ("third_party_verifier",)
    if req.is_emergency:
        observer = observer + ("incident_command",)

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
    original_request: EnvironmentalRequest,
) -> EnvironmentalResult:
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
        [f"officer: {original_request.responsible_officer}"]
        + [f"reviewer: {r}" for r in original_request.reviewer_chain]
    )

    return EnvironmentalResult(
        stewardship_protocol=protocol,
        required_signoffs=signoffs,
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        third_party_verified=original_request.third_party_verified,
        is_emergency=original_request.is_emergency,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- run_with_ucja ----


def _request_to_ucja_payload(req: EnvironmentalRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "environmental_action",
    }


def run_with_ucja(
    req: EnvironmentalRequest,
    *,
    capture: list | None = None,
) -> EnvironmentalResult:
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
        causation_mechanism="environmental_action",
        causation_strength=0.92,
        transformation_energy=1.0,
        transformation_reversibility=_reversibility_for_kind(req.kind),
        validation_evidence_refs=_evidence_refs_for_request(req),
        validation_confidence=0.93,
        observation_sensor="emissions_monitor",
        observation_signal="reading" if req.kind == EnvironmentalActionKind.EMISSIONS_REPORTING else "logged",
        observation_confidence=0.96,
        inference_rule="permit_or_disclosure_standard",
        inference_certainty=0.9,
        inference_kind="deductive",
        decision_criteria=(
            "acceptance_criteria_satisfied",
            "no_unmitigated_exceedance",
        ),
        decision_justification=(
            f"environmental action {req.kind.value} for facility "
            f"{req.facility_id} ({req.regulatory_authority or 'unspecified authority'})"
        ),
        execution_plan_prefix=f"execute {req.kind.value} for facility {req.facility_id}",
        execution_resources=tuple(req.affected_media),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: EnvironmentalActionKind, summary: str) -> str:
    verb_map = {
        EnvironmentalActionKind.EMISSIONS_REPORTING:     "report_emissions_to_inventory",
        EnvironmentalActionKind.PERMIT_COMPLIANCE_CHECK: "verify_compliance_with_permit",
        EnvironmentalActionKind.AUDIT:                   "evaluate_environmental_management_system",
        EnvironmentalActionKind.REMEDIATION_PLAN:        "design_corrective_action",
        EnvironmentalActionKind.REMEDIATION_EXECUTION:   "execute_corrective_action",
        EnvironmentalActionKind.INCIDENT_RESPONSE:       "respond_to_acute_environmental_event",
        EnvironmentalActionKind.DISCLOSURE_FILING:       "file_assured_sustainability_disclosure",
        EnvironmentalActionKind.CARBON_OFFSET_PURCHASE:  "acquire_emission_reduction_units",
        EnvironmentalActionKind.IMPACT_ASSESSMENT:       "assess_action_environmental_impact",
        EnvironmentalActionKind.CONSENT_DECREE_ACTION:   "perform_court_ordered_obligation",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "facility":  "closed",
        "watershed": "selective",
        "airshed":   "selective",
        "regional":  "open",
    }.get(blast, "selective")


def _reversibility_for_kind(kind: EnvironmentalActionKind) -> str:
    if kind in (
        EnvironmentalActionKind.DISCLOSURE_FILING,
        EnvironmentalActionKind.CONSENT_DECREE_ACTION,
        EnvironmentalActionKind.CARBON_OFFSET_PURCHASE,
        EnvironmentalActionKind.REMEDIATION_EXECUTION,
    ):
        return "irreversible"
    if kind in (
        EnvironmentalActionKind.EMISSIONS_REPORTING,
        EnvironmentalActionKind.PERMIT_COMPLIANCE_CHECK,
        EnvironmentalActionKind.AUDIT,
        EnvironmentalActionKind.REMEDIATION_PLAN,
        EnvironmentalActionKind.IMPACT_ASSESSMENT,
        EnvironmentalActionKind.INCIDENT_RESPONSE,
    ):
        return "reversible"
    return "unknown"


def _evidence_refs_for_request(req: EnvironmentalRequest) -> tuple[str, ...]:
    refs: list[str] = ["ehs_record"]
    if req.kind == EnvironmentalActionKind.EMISSIONS_REPORTING:
        refs.append("emissions_inventory")
    if req.kind == EnvironmentalActionKind.AUDIT:
        refs.append("audit_findings_report")
    if req.kind == EnvironmentalActionKind.DISCLOSURE_FILING:
        refs.append("verified_disclosure_document")
    if req.kind == EnvironmentalActionKind.CARBON_OFFSET_PURCHASE:
        refs.append("offset_retirement_certificate")
    if req.kind == EnvironmentalActionKind.IMPACT_ASSESSMENT:
        refs.append("impact_study")
    if req.third_party_verified:
        refs.append("verification_statement")
    if req.is_emergency:
        refs.append("incident_log")
    return tuple(refs)


def _protocol_from_constructs(
    summary: dict[str, int],
    req: EnvironmentalRequest,
) -> tuple[str, ...]:
    steps: list[str] = []
    if summary.get("observation", 0) > 0:
        steps.append(f"Capture initial environmental state for facility {req.facility_id}")
    if summary.get("inference", 0) > 0:
        steps.append("Apply permit conditions and disclosure standards to data")
    if summary.get("decision", 0) > 0:
        steps.append("Decide on environmental action")
    if summary.get("transformation", 0) > 0:
        steps.append(f"Execute {req.kind.value}")
    if req.exceedance_present:
        if req.kind in _RESPONSE_KINDS:
            steps.append(
                "Active exceedance — proceed with response action"
            )
        elif req.is_emergency:
            steps.append(
                "Active exceedance under declared emergency — escalate"
            )
        else:
            steps.append(
                "Block: routine action attempted during active exceedance"
            )
    if req.environmental_justice_concern:
        steps.append(
            "Environmental-justice review for affected community"
        )
    if req.third_party_verified:
        steps.append("Confirm third-party verification statement on file")
    elif req.kind == EnvironmentalActionKind.DISCLOSURE_FILING:
        steps.append("Block: third-party verification missing for disclosure")
    for r in req.reviewer_chain:
        steps.append(f"Reviewer signoff: {r}")
    if summary.get("validation", 0) > 0:
        steps.append("Validate against acceptance criteria")
    if req.kind == EnvironmentalActionKind.DISCLOSURE_FILING:
        steps.append("File assured disclosure with regulator and registry")
    elif req.kind == EnvironmentalActionKind.INCIDENT_RESPONSE:
        steps.append("Notify authorities and affected communities of incident")
    elif req.kind == EnvironmentalActionKind.CARBON_OFFSET_PURCHASE:
        steps.append("Retire offsets in registry and record certificate")
    elif req.kind == EnvironmentalActionKind.REMEDIATION_EXECUTION:
        steps.append("Execute remedial action and sample post-remediation")
    elif req.kind == EnvironmentalActionKind.CONSENT_DECREE_ACTION:
        steps.append("Document compliance with consent-decree provision")
    if summary.get("execution", 0) > 0:
        steps.append("Persist event to environmental management system")
    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: EnvironmentalRequest,
) -> tuple[str, ...]:
    flags: list[str] = []
    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")
    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")
    if result.proof_state == "Unknown":
        flags.append("environmental_evidence_insufficient")
    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted")

    if req.exceedance_present:
        if req.kind in _RESPONSE_KINDS:
            flags.append(
                f"active_exceedance_during_{req.kind.value} — "
                "verify response is bringing system into compliance"
            )
        elif req.is_emergency:
            flags.append(
                "active_exceedance_under_emergency — document declaration "
                "and post-event review path"
            )
        else:
            flags.append(
                "active_exceedance_routine_action — block until exceedance "
                "resolved or emergency declared"
            )
    if req.environmental_justice_concern:
        flags.append(
            "environmental_justice_concern — heightened review for "
            "disproportionate impact on protected community"
        )
    if (
        req.kind == EnvironmentalActionKind.DISCLOSURE_FILING
        and not req.third_party_verified
    ):
        flags.append(
            "disclosure_without_third_party_verification — block until "
            "assurance complete"
        )
    if req.is_emergency:
        flags.append(
            "incident_response_posture — verify notification clocks "
            "and regulator engagement"
        )
    if req.blast_radius == "regional":
        flags.append(
            "regional_blast_radius — cross-jurisdiction or cross-media "
            "impact; engage upstream/downstream regulators"
        )
    if req.kind in (
        EnvironmentalActionKind.DISCLOSURE_FILING,
        EnvironmentalActionKind.CONSENT_DECREE_ACTION,
        EnvironmentalActionKind.CARBON_OFFSET_PURCHASE,
        EnvironmentalActionKind.REMEDIATION_EXECUTION,
    ):
        flags.append(
            f"{req.kind.value}_irreversible — confirm before execution"
        )
    if (
        req.kind == EnvironmentalActionKind.EMISSIONS_REPORTING
        and not req.third_party_verified
    ):
        flags.append(
            "emissions_reporting_without_third_party_verification — "
            "consider assurance for credibility"
        )
    if (
        len(req.affected_media) > 1
    ):
        flags.append(
            f"cross_media_impact ({', '.join(req.affected_media)}) — "
            "coordinate across media-specific permits"
        )
    return tuple(flags)
