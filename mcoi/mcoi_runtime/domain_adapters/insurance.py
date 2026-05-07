"""
Insurance Domain Adapter.

Translates insurance actions (underwriting, policy binding, claim
intake, claim adjudication, claim payment, renewal, cancellation,
rescission, reinsurance cession, regulatory filing) into the universal
causal framework. Distinct shape:

  - Authority chain: responsible agent (underwriter for u/w kinds,
    adjuster for claims kinds) + approver chain (senior u/w, claims
    supervisor). State DOI / NAIC regulators and the actuarial review
    function are observer-shaped — they witness but do not authorize.
  - Constraints carry acceptance criteria, sanctions screening,
    over-limit detection, and reinsurance-cession requirements — each
    with different violation_response. Sanctions hits are a hard
    block (cannot bind or pay a sanctioned party, ever — emergencies
    do NOT relax this). Over-limit claims block until adjusted.
  - Many actions are irreversible once issued or paid (bind_policy,
    claim_payment, regulatory_filing, reinsurance_cession,
    cancellation, rescission). Underwriting review, claim intake,
    claim adjudication, and renewal remain reversible — decisions
    can be revisited.
  - Risk flags surface sanctions hits, over-limit exposure, missing
    reinsurance on large risks, missing regulator on filings, and
    book-level / systemic blast radius.

This adapter intentionally does NOT model rate calculations, loss
reserving, or specific policy form interpretation — it models the
governance shape, and leaves jurisdiction-specific rules (state
insurance codes, NAIC model laws, IFRS-17, GAAP) to the calling
system.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
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


class InsuranceActionKind(Enum):
    UNDERWRITING = "underwriting"
    BIND_POLICY = "bind_policy"
    CLAIM_INTAKE = "claim_intake"
    CLAIM_ADJUDICATION = "claim_adjudication"
    CLAIM_PAYMENT = "claim_payment"
    RENEWAL = "renewal"
    CANCELLATION = "cancellation"
    RESCISSION = "rescission"
    REINSURANCE_CESSION = "reinsurance_cession"
    REGULATORY_FILING = "regulatory_filing"


_UNDERWRITING_KINDS = (
    InsuranceActionKind.UNDERWRITING,
    InsuranceActionKind.BIND_POLICY,
    InsuranceActionKind.RENEWAL,
    InsuranceActionKind.CANCELLATION,
    InsuranceActionKind.RESCISSION,
    InsuranceActionKind.REINSURANCE_CESSION,
)

_CLAIMS_KINDS = (
    InsuranceActionKind.CLAIM_INTAKE,
    InsuranceActionKind.CLAIM_ADJUDICATION,
    InsuranceActionKind.CLAIM_PAYMENT,
)


@dataclass
class InsuranceRequest:
    kind: InsuranceActionKind
    summary: str
    case_id: str  # policy or claim case
    responsible_agent: str  # underwriter or adjuster depending on kind
    approver_chain: tuple[str, ...] = ()
    policyholder: str = ""
    line_of_business: str = ""  # auto | home | commercial | life | health
    jurisdiction: str = ""  # e.g. "US-CA", "EU"
    regulatory_regime: tuple[str, ...] = ()  # e.g. ("NAIC","CA-DOI")
    policy_number: str = ""
    claim_number: str = ""  # empty for non-claim actions
    sum_insured: Decimal = Decimal("0")
    claim_amount: Decimal = Decimal("0")
    affected_policies: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    sanctions_screened: bool = False
    sanctions_hits: tuple[str, ...] = ()  # OFAC/PEP/etc. hits
    reinsurance_required: bool = False
    reinsurance_engaged: bool = False
    is_emergency: bool = False  # catastrophe response posture
    blast_radius: str = "policy"  # policy | policyholder | book | systemic


@dataclass
class InsuranceResult:
    handling_protocol: tuple[str, ...]
    required_signoffs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    sanctions_clear: bool
    is_emergency: bool
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


def translate_to_universal(req: InsuranceRequest) -> UniversalRequest:
    if req.sum_insured < 0:
        raise ValueError(
            f"sum_insured {req.sum_insured!r} must be non-negative"
        )
    if req.claim_amount < 0:
        raise ValueError(
            f"claim_amount {req.claim_amount!r} must be non-negative"
        )
    if req.kind in _CLAIMS_KINDS and not req.claim_number:
        raise ValueError(
            f"claims action {req.kind.value!r} requires a claim_number"
        )

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "insurance_state",
        "case_id": req.case_id,
        "phase": "pre_action",
        "responsible_agent": req.responsible_agent,
        "policyholder": req.policyholder,
        "line_of_business": req.line_of_business,
    }
    target_state = {
        "kind": "insurance_state",
        "case_id": req.case_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "sanctions_clear": (
            req.sanctions_screened and not req.sanctions_hits
        ),
    }
    boundary = {
        "inside_predicate": (
            f"case_id = {req.case_id} ∧ "
            f"line_of_business = {req.line_of_business or '<unspecified>'}"
        ),
        "interface_points": list(req.affected_policies),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "insurance_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]

    # Sanctions — hard block. No emergency override (sanctions are
    # absolute under OFAC/UN/EU regimes; relief comes from licensing,
    # not adapter-level relaxation).
    for hit in req.sanctions_hits:
        constraints.append(
            {
                "domain": "sanctions",
                "restriction": f"sanctions_clearance:{hit}",
                "violation_response": "block",
            }
        )

    # Over-limit claim — claim_amount may not exceed sum_insured for
    # claim_payment. Block until adjusted (or excess of loss reinsurance
    # engaged, which is policy-specific and modeled by caller).
    if (
        req.kind == InsuranceActionKind.CLAIM_PAYMENT
        and req.sum_insured > 0
        and req.claim_amount > req.sum_insured
    ):
        constraints.append(
            {
                "domain": "policy_limit",
                "restriction": "claim_within_sum_insured",
                "violation_response": "block",
            }
        )

    # Reinsurance cession — large risks must engage reinsurer before
    # bind. Escalate (not block) since some lines self-insure to a
    # threshold; caller decides the threshold.
    if req.reinsurance_required and not req.reinsurance_engaged:
        constraints.append(
            {
                "domain": "reinsurance",
                "restriction": "reinsurer_engaged_before_bind",
                "violation_response": "escalate",
            }
        )

    # Catastrophe / emergency posture — record but do not relax other
    # constraints. The acceptance_criteria can include "expedited
    # review documented", which is the calling system's hook.
    # No constraint added here; observer entry below records emergency.

    authority = (
        f"agent:{req.responsible_agent}",
    ) + tuple(f"approver:{a}" for a in req.approver_chain)

    observer: tuple[str, ...] = ("policy_audit",)
    if req.line_of_business:
        observer = observer + (f"line_of_business:{req.line_of_business}",)
    if req.jurisdiction:
        observer = observer + (f"jurisdiction:{req.jurisdiction}",)
    for regime in req.regulatory_regime:
        observer = observer + (f"regulator:{regime}",)
    if req.policyholder:
        observer = observer + (f"policyholder:{req.policyholder}",)
    if req.sanctions_screened:
        observer = observer + ("sanctions_compliance",)
    if req.reinsurance_required and req.reinsurance_engaged:
        observer = observer + ("reinsurer",)
    if req.is_emergency:
        observer = observer + ("catastrophe_response_log",)
    # Actuarial review for large or claims actions
    if (
        req.sum_insured >= Decimal("1000000")
        or req.kind == InsuranceActionKind.CLAIM_ADJUDICATION
    ):
        observer = observer + ("actuarial_review",)

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
    original_request: InsuranceRequest,
) -> InsuranceResult:
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
        [f"agent: {original_request.responsible_agent}"]
        + [f"approver: {a}" for a in original_request.approver_chain]
    )

    return InsuranceResult(
        handling_protocol=protocol,
        required_signoffs=signoffs,
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        sanctions_clear=(
            original_request.sanctions_screened
            and not original_request.sanctions_hits
        ),
        is_emergency=original_request.is_emergency,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- run_with_ucja ----


def _request_to_ucja_payload(req: InsuranceRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "insurance_action",
    }


def run_with_ucja(
    req: InsuranceRequest,
    *,
    capture: list | None = None,
) -> InsuranceResult:
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
        causation_mechanism="insurance_action",
        causation_strength=0.93,
        transformation_energy=1.0,
        transformation_reversibility=_reversibility_for_kind(req.kind),
        validation_evidence_refs=_evidence_refs_for_request(req),
        validation_confidence=0.95,
        observation_sensor="policy_admin_system",
        observation_signal="recorded",
        observation_confidence=0.98,
        inference_rule="policy_form_or_actuarial_table",
        inference_certainty=0.92,
        inference_kind="deductive",  # policy applies to facts
        decision_criteria=(
            "acceptance_criteria_satisfied",
            "sanctions_clear_or_screened",
        ),
        decision_justification=(
            f"insurance action {req.kind.value} for case {req.case_id} "
            f"({req.line_of_business or 'unspecified LOB'})"
        ),
        execution_plan_prefix=f"execute {req.kind.value} for case {req.case_id}",
        execution_resources=tuple(req.affected_policies),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: InsuranceActionKind, summary: str) -> str:
    verb_map = {
        InsuranceActionKind.UNDERWRITING:        "evaluate_risk_for_coverage",
        InsuranceActionKind.BIND_POLICY:         "issue_binding_coverage",
        InsuranceActionKind.CLAIM_INTAKE:        "record_first_notice_of_loss",
        InsuranceActionKind.CLAIM_ADJUDICATION:  "determine_coverage_for_claim",
        InsuranceActionKind.CLAIM_PAYMENT:       "disburse_indemnity_to_payee",
        InsuranceActionKind.RENEWAL:             "extend_coverage_for_next_term",
        InsuranceActionKind.CANCELLATION:        "terminate_coverage_prospectively",
        InsuranceActionKind.RESCISSION:          "void_coverage_ab_initio",
        InsuranceActionKind.REINSURANCE_CESSION: "cede_risk_to_reinsurer",
        InsuranceActionKind.REGULATORY_FILING:   "file_required_regulator_form",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "policy":       "closed",
        "policyholder": "selective",
        "book":         "selective",
        "systemic":     "open",
    }.get(blast, "selective")


def _reversibility_for_kind(kind: InsuranceActionKind) -> str:
    if kind in (
        InsuranceActionKind.BIND_POLICY,
        InsuranceActionKind.CLAIM_PAYMENT,
        InsuranceActionKind.REGULATORY_FILING,
        InsuranceActionKind.REINSURANCE_CESSION,
        InsuranceActionKind.CANCELLATION,
        InsuranceActionKind.RESCISSION,
    ):
        return "irreversible"
    if kind in (
        InsuranceActionKind.UNDERWRITING,
        InsuranceActionKind.CLAIM_INTAKE,
        InsuranceActionKind.CLAIM_ADJUDICATION,
        InsuranceActionKind.RENEWAL,
    ):
        return "reversible"
    return "unknown"


def _evidence_refs_for_request(req: InsuranceRequest) -> tuple[str, ...]:
    refs: list[str] = ["policy_admin_record"]
    if req.sanctions_screened:
        refs.append("sanctions_screening_report")
    if req.kind in _CLAIMS_KINDS:
        refs.append("loss_documentation")
    if req.kind == InsuranceActionKind.CLAIM_PAYMENT:
        refs.append("payment_authorization")
    if req.kind == InsuranceActionKind.UNDERWRITING:
        refs.append("risk_assessment_worksheet")
    if req.kind == InsuranceActionKind.REGULATORY_FILING:
        refs.append("regulatory_filing_receipt")
    if req.reinsurance_engaged:
        refs.append("reinsurance_treaty")
    return tuple(refs)


def _protocol_from_constructs(
    summary: dict[str, int],
    req: InsuranceRequest,
) -> tuple[str, ...]:
    steps: list[str] = []
    if summary.get("observation", 0) > 0:
        steps.append(f"Open case record for {req.case_id}")
    if summary.get("inference", 0) > 0:
        steps.append("Apply policy form and actuarial guidance to facts")
    if summary.get("decision", 0) > 0:
        steps.append("Decide on insurance action")
    if summary.get("transformation", 0) > 0:
        steps.append(f"Execute {req.kind.value}")
    if req.sanctions_screened:
        if req.sanctions_hits:
            steps.append(
                f"Block: sanctions hit(s) present "
                f"({', '.join(req.sanctions_hits)})"
            )
        else:
            steps.append("Sanctions screening clear")
    if req.reinsurance_required:
        if req.reinsurance_engaged:
            steps.append("Confirm reinsurance treaty in force")
        else:
            steps.append("Engage reinsurer before bind")
    for a in req.approver_chain:
        steps.append(f"Approver signoff: {a}")
    if req.is_emergency:
        steps.append(
            "Catastrophe-response posture: document expedited review"
        )
    if summary.get("validation", 0) > 0:
        steps.append("Validate against acceptance criteria")
    if req.kind == InsuranceActionKind.BIND_POLICY:
        steps.append("Issue declaration page and policy form to policyholder")
    elif req.kind == InsuranceActionKind.CLAIM_PAYMENT:
        steps.append("Disburse indemnity to payee of record")
    elif req.kind == InsuranceActionKind.CANCELLATION:
        steps.append("Issue notice of cancellation per jurisdiction rules")
    elif req.kind == InsuranceActionKind.RESCISSION:
        steps.append("Issue notice of rescission and refund premium")
    elif req.kind == InsuranceActionKind.REGULATORY_FILING:
        steps.append("File required form with insurance regulator")
    elif req.kind == InsuranceActionKind.REINSURANCE_CESSION:
        steps.append("Record cession to reinsurer in cession bordereau")
    if summary.get("execution", 0) > 0:
        steps.append("Persist event to policy admin and accounting systems")
    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: InsuranceRequest,
) -> tuple[str, ...]:
    flags: list[str] = []
    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")
    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")
    if result.proof_state == "Unknown":
        flags.append("insurance_evidence_insufficient")
    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted")

    if req.sanctions_hits:
        flags.append(
            f"sanctions_hits_present ({', '.join(req.sanctions_hits)}) — "
            "absolute block; only specific licensing can permit action"
        )
    if (
        req.kind == InsuranceActionKind.CLAIM_PAYMENT
        and req.sum_insured > 0
        and req.claim_amount > req.sum_insured
    ):
        flags.append(
            f"claim_exceeds_sum_insured "
            f"(claim={req.claim_amount}, limit={req.sum_insured}) — "
            "block until adjusted"
        )
    if req.reinsurance_required and not req.reinsurance_engaged:
        flags.append(
            "reinsurance_required_but_not_engaged — engage reinsurer "
            "before bind"
        )
    if (
        req.kind in _UNDERWRITING_KINDS
        and req.sum_insured == 0
    ):
        flags.append(
            f"{req.kind.value}_with_zero_sum_insured — verify "
            "exposure is intentional"
        )
    if req.is_emergency:
        flags.append(
            "catastrophe_response_posture — verify CAT declaration and "
            "expedited review path"
        )
    if (
        req.kind == InsuranceActionKind.REGULATORY_FILING
        and not req.regulatory_regime
    ):
        flags.append(
            "regulatory_filing_without_regime — verify filing venue"
        )
    if req.blast_radius == "systemic":
        flags.append(
            "systemic_blast_radius — book or industry impact; senior "
            "management review"
        )
    if req.kind in (
        InsuranceActionKind.BIND_POLICY,
        InsuranceActionKind.CLAIM_PAYMENT,
        InsuranceActionKind.REGULATORY_FILING,
        InsuranceActionKind.REINSURANCE_CESSION,
        InsuranceActionKind.CANCELLATION,
        InsuranceActionKind.RESCISSION,
    ):
        flags.append(
            f"{req.kind.value}_irreversible — confirm before issuance"
        )
    return tuple(flags)
