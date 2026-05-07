"""
Public Sector / Government Domain Adapter.

Translates civic actions (permit issuance, benefit claims, policy
enforcement, inspections, licensing, rulemaking, citizen service
requests, enforcement actions, grant awards, records requests) into
the universal causal framework. Distinct shape:

  - Authority chain: responsible official + reviewer chain. The AGENCY,
    statutory authority, and ombudsman are observer-shaped requirements
    that do not slot into the same approval hierarchy.
  - Constraints carry acceptance criteria, due-process requirements
    (notice + hearing), public-comment requirements (rulemaking), and
    protected-class flags — each with different violation_response.
    Due process is a hard block; public comment relaxes to escalate
    under declared emergency.
  - Many actions are structurally irreversible once promulgated or
    awarded (rulemaking, permit_issuance, licensing, grant_award,
    enforcement_action). The reviewing/processing actions
    (benefit_claim, records_request, inspection) remain reversible —
    a denial can be re-decided on appeal.
  - Risk flags surface missing due process, missing public comment,
    protected-class involvement without escalation, statutory authority
    not specified, and systemic blast radius (precedent / policy).

This adapter intentionally does NOT model substantive administrative
law or codify specific agency procedures — it models the governance
shape, and leaves jurisdiction-specific rules (APA, agency regs,
state administrative codes) to the calling system.
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


class CivicActionKind(Enum):
    PERMIT_ISSUANCE = "permit_issuance"
    LICENSING = "licensing"
    BENEFIT_CLAIM = "benefit_claim"
    GRANT_AWARD = "grant_award"
    POLICY_ENFORCEMENT = "policy_enforcement"
    ENFORCEMENT_ACTION = "enforcement_action"
    INSPECTION = "inspection"
    RULEMAKING = "rulemaking"
    CITIZEN_SERVICE_REQUEST = "citizen_service_request"
    RECORDS_REQUEST = "records_request"


@dataclass
class CivicRequest:
    kind: CivicActionKind
    summary: str
    case_id: str
    responsible_official: str
    reviewer_chain: tuple[str, ...] = ()
    applicant: str = ""  # citizen / entity making the request
    agency: str = ""  # issuing agency, e.g. "EPA", "DMV-CA"
    statute_authority: tuple[str, ...] = ()  # e.g. ("APA","5_USC_552")
    jurisdiction: str = ""  # "US-FED" | "US-CA" | "US-CA-LA"
    affected_records: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    due_process_required: bool = False
    due_process_completed: bool = False
    public_comment_required: bool = False
    public_comment_completed: bool = False
    protected_class_present: tuple[str, ...] = ()  # e.g. ("disability","minor")
    is_emergency: bool = False  # declared emergency (relaxes some procedure)
    blast_radius: str = "case"  # case | applicant | constituency | systemic


@dataclass
class CivicResult:
    civic_protocol: tuple[str, ...]
    required_signoffs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    due_process_satisfied: bool
    public_comment_satisfied: bool
    is_emergency: bool
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


_RULEMAKING_KINDS = (CivicActionKind.RULEMAKING,)
_ADJUDICATIVE_KINDS = (
    CivicActionKind.PERMIT_ISSUANCE,
    CivicActionKind.LICENSING,
    CivicActionKind.BENEFIT_CLAIM,
    CivicActionKind.GRANT_AWARD,
    CivicActionKind.ENFORCEMENT_ACTION,
)


def translate_to_universal(req: CivicRequest) -> UniversalRequest:
    if req.kind in _RULEMAKING_KINDS and not req.statute_authority:
        raise ValueError(
            f"rulemaking requires statute_authority granting power "
            f"(case_id={req.case_id})"
        )

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "civic_state",
        "case_id": req.case_id,
        "phase": "pre_action",
        "responsible_official": req.responsible_official,
        "applicant": req.applicant,
        "agency": req.agency,
    }
    target_state = {
        "kind": "civic_state",
        "case_id": req.case_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "due_process_satisfied": req.due_process_completed,
        "public_comment_satisfied": req.public_comment_completed,
    }
    boundary = {
        "inside_predicate": (
            f"case_id = {req.case_id} ∧ "
            f"agency = {req.agency or '<unspecified>'}"
        ),
        "interface_points": list(req.affected_records),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "civic_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]

    # Due process — notice + hearing. Hard block on adjudicative actions
    # when required but not completed. Even declared emergency does NOT
    # waive due process (deprivation of property/liberty without process
    # is unconstitutional regardless of urgency); emergency only short-
    # circuits the timing of pre-deprivation hearing in narrow cases,
    # which the calling system models, not this adapter.
    if req.due_process_required and not req.due_process_completed:
        constraints.append(
            {
                "domain": "due_process",
                "restriction": "notice_and_hearing_completed",
                "violation_response": "block",
            }
        )

    # Public comment — APA-style notice-and-comment. Required for
    # rulemaking. Declared emergency relaxes block to escalate
    # (interim final rule pathway).
    if req.public_comment_required and not req.public_comment_completed:
        pc_response = "escalate" if req.is_emergency else "block"
        constraints.append(
            {
                "domain": "public_comment",
                "restriction": "notice_and_comment_period_completed",
                "violation_response": pc_response,
            }
        )

    # Protected-class involvement — escalate for heightened review
    # (e.g. disability accommodation, minor protections, language
    # access). Each class becomes its own escalation.
    for pc in req.protected_class_present:
        constraints.append(
            {
                "domain": "protected_class",
                "restriction": f"heightened_review:{pc}",
                "violation_response": "escalate",
            }
        )

    authority = (
        f"official:{req.responsible_official}",
    ) + tuple(f"reviewer:{r}" for r in req.reviewer_chain)

    observer: tuple[str, ...] = ("civic_audit", "ombudsman")
    if req.agency:
        observer = observer + (f"agency:{req.agency}",)
    if req.jurisdiction:
        observer = observer + (f"jurisdiction:{req.jurisdiction}",)
    for s in req.statute_authority:
        observer = observer + (f"statute:{s}",)
    if req.applicant:
        observer = observer + (f"applicant:{req.applicant}",)
    if req.public_comment_required and req.public_comment_completed:
        observer = observer + ("public_record",)

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
    original_request: CivicRequest,
) -> CivicResult:
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
        [f"official: {original_request.responsible_official}"]
        + [f"reviewer: {r}" for r in original_request.reviewer_chain]
    )

    return CivicResult(
        civic_protocol=protocol,
        required_signoffs=signoffs,
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        due_process_satisfied=(
            original_request.due_process_completed
            if original_request.due_process_required
            else True
        ),
        public_comment_satisfied=(
            original_request.public_comment_completed
            if original_request.public_comment_required
            else True
        ),
        is_emergency=original_request.is_emergency,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- run_with_ucja ----


def _request_to_ucja_payload(req: CivicRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "civic_action",
    }


def run_with_ucja(
    req: CivicRequest,
    *,
    capture: list | None = None,
) -> CivicResult:
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
        causation_mechanism="civic_action",
        causation_strength=0.9,
        transformation_energy=1.0,
        transformation_reversibility=_reversibility_for_kind(req.kind),
        validation_evidence_refs=_evidence_refs_for_request(req),
        validation_confidence=0.93,
        observation_sensor="case_record_observation",
        observation_signal="docketed",
        observation_confidence=0.97,
        inference_rule="statutory_authority",
        inference_certainty=0.9,
        inference_kind="deductive",  # admin law applies stat to facts
        decision_criteria=(
            "acceptance_criteria_satisfied",
            "due_process_or_not_required",
        ),
        decision_justification=(
            f"civic action {req.kind.value} for case {req.case_id} "
            f"by {req.agency or 'unspecified agency'}"
        ),
        execution_plan_prefix=f"execute {req.kind.value} for case {req.case_id}",
        execution_resources=tuple(req.affected_records),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: CivicActionKind, summary: str) -> str:
    verb_map = {
        CivicActionKind.PERMIT_ISSUANCE:         "grant_authorization_to_act",
        CivicActionKind.LICENSING:               "confer_regulated_status",
        CivicActionKind.BENEFIT_CLAIM:           "adjudicate_entitlement",
        CivicActionKind.GRANT_AWARD:             "disburse_public_funds",
        CivicActionKind.POLICY_ENFORCEMENT:      "apply_policy_to_circumstance",
        CivicActionKind.ENFORCEMENT_ACTION:      "impose_penalty_or_remedy",
        CivicActionKind.INSPECTION:              "verify_compliance_in_place",
        CivicActionKind.RULEMAKING:              "promulgate_administrative_rule",
        CivicActionKind.CITIZEN_SERVICE_REQUEST: "deliver_citizen_service",
        CivicActionKind.RECORDS_REQUEST:         "respond_to_records_disclosure_request",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "case":         "closed",
        "applicant":    "selective",
        "constituency": "selective",
        "systemic":     "open",  # precedent / policy
    }.get(blast, "selective")


def _reversibility_for_kind(kind: CivicActionKind) -> str:
    if kind in (
        CivicActionKind.PERMIT_ISSUANCE,
        CivicActionKind.LICENSING,
        CivicActionKind.GRANT_AWARD,
        CivicActionKind.ENFORCEMENT_ACTION,
        CivicActionKind.RULEMAKING,
    ):
        return "irreversible"
    if kind in (
        CivicActionKind.BENEFIT_CLAIM,
        CivicActionKind.CITIZEN_SERVICE_REQUEST,
        CivicActionKind.RECORDS_REQUEST,
        CivicActionKind.INSPECTION,
        CivicActionKind.POLICY_ENFORCEMENT,
    ):
        return "reversible"
    return "unknown"


def _evidence_refs_for_request(req: CivicRequest) -> tuple[str, ...]:
    refs: list[str] = ["case_record"]
    if req.due_process_required and req.due_process_completed:
        refs.append("notice_and_hearing_record")
    if req.public_comment_required and req.public_comment_completed:
        refs.append("public_comment_docket")
    if req.kind == CivicActionKind.INSPECTION:
        refs.append("inspection_report")
    if req.kind == CivicActionKind.RECORDS_REQUEST:
        refs.append("records_index")
    if req.statute_authority:
        refs.append("statutory_citation")
    return tuple(refs)


def _protocol_from_constructs(
    summary: dict[str, int],
    req: CivicRequest,
) -> tuple[str, ...]:
    steps: list[str] = []
    if summary.get("observation", 0) > 0:
        steps.append(f"Open case record for {req.case_id}")
    if summary.get("inference", 0) > 0:
        steps.append("Apply statutory authority and agency policy to the facts")
    if summary.get("decision", 0) > 0:
        steps.append("Decide on the civic action")
    if summary.get("transformation", 0) > 0:
        steps.append(f"Execute {req.kind.value}")
    if req.due_process_required:
        if req.due_process_completed:
            steps.append("Confirm notice-and-hearing record on file")
        else:
            steps.append("Block: notice-and-hearing not completed")
    if req.public_comment_required:
        if req.public_comment_completed:
            steps.append("Confirm public comment docket closed")
        elif req.is_emergency:
            steps.append("Issue interim final rule under emergency authority")
        else:
            steps.append("Block: public comment period not completed")
    for r in req.reviewer_chain:
        steps.append(f"Reviewer signoff: {r}")
    if req.protected_class_present:
        steps.append(
            f"Heightened review for protected class(es): "
            f"{', '.join(req.protected_class_present)}"
        )
    if summary.get("validation", 0) > 0:
        steps.append("Validate decision against acceptance criteria")
    if req.kind == CivicActionKind.PERMIT_ISSUANCE:
        steps.append("Issue permit and post to public registry")
    elif req.kind == CivicActionKind.RULEMAKING:
        steps.append("Publish final rule in agency register")
    elif req.kind == CivicActionKind.ENFORCEMENT_ACTION:
        steps.append("Serve notice of violation and right to appeal")
    elif req.kind == CivicActionKind.GRANT_AWARD:
        steps.append("Disburse funds and record obligation")
    elif req.kind == CivicActionKind.RECORDS_REQUEST:
        steps.append("Produce responsive records (with redactions if required)")
    elif req.kind == CivicActionKind.INSPECTION:
        steps.append("File inspection report and notify subject")
    if summary.get("execution", 0) > 0:
        steps.append("Persist final action to case file and ombudsman log")
    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: CivicRequest,
) -> tuple[str, ...]:
    flags: list[str] = []
    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")
    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")
    if result.proof_state == "Unknown":
        flags.append("statutory_authority_insufficient")
    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted")

    if req.due_process_required and not req.due_process_completed:
        flags.append(
            "due_process_required_but_not_completed — block until "
            "notice and hearing recorded"
        )
    if req.public_comment_required and not req.public_comment_completed:
        if req.is_emergency:
            flags.append(
                "public_comment_pending_under_emergency — interim final "
                "rule pathway requires post-promulgation comment window"
            )
        else:
            flags.append(
                "public_comment_required_but_not_completed — block until "
                "comment period closes"
            )
    if req.protected_class_present:
        flags.append(
            f"protected_class_involved ({', '.join(req.protected_class_present)}) — "
            "heightened review required"
        )
    if req.is_emergency:
        flags.append(
            "emergency_mode — declared emergency posture; document "
            "factual predicate"
        )
    if req.kind in _ADJUDICATIVE_KINDS and not req.statute_authority:
        flags.append(
            f"{req.kind.value}_without_statute_authority — verify "
            "agency power to act"
        )
    if req.blast_radius == "systemic":
        flags.append(
            "systemic_blast_radius — precedent / policy effect; "
            "agency leadership review"
        )
    if req.kind in (
        CivicActionKind.PERMIT_ISSUANCE,
        CivicActionKind.LICENSING,
        CivicActionKind.GRANT_AWARD,
        CivicActionKind.ENFORCEMENT_ACTION,
        CivicActionKind.RULEMAKING,
    ):
        flags.append(
            f"{req.kind.value}_irreversible — confirm before issuance"
        )
    if (
        req.kind == CivicActionKind.RECORDS_REQUEST
        and not req.affected_records
    ):
        flags.append(
            "records_request_without_record_set — verify scope or "
            "issue no-records response"
        )
    return tuple(flags)
