"""
Legal Domain Adapter.

Translates legal actions (case filings, contract review/execution,
motions, discovery, judgments, appeals, compliance review, legal
opinions) into the universal causal framework. Distinct shape:

  - Authority chain: lead counsel + co-counsel; the COURT, the
    JURISDICTION, and the CLIENT are observer-shaped requirements that
    do not slot into the same role hierarchy.
  - Constraints carry acceptance criteria, conflict-of-interest checks,
    statute-of-limitations urgency, and bar-admission requirements —
    each with different violation_response (block / escalate / warn).
  - Many actions are structurally irreversible once the act-of-filing
    or act-of-service occurs (case_filing, motion, judgment, appeal,
    contract_execution, deposition, discovery production). The
    reviewing/advisory actions (contract_review, compliance_review,
    opinion) remain reversible — the work product can be revised
    before it leaves counsel's hands.
  - Risk flags surface conflicts of interest, missing privilege logs
    on privileged work, statute deadline pressure, missing bar
    admissions, and systemic blast radius (precedent-setting).

This adapter intentionally does NOT model substantive legal doctrine
or codify specific procedural rules — it models the governance shape,
and leaves jurisdiction-specific rules (FRCP, local rules, ABA Model
Rules) to the calling system. The acceptance_criteria list is where
domain-specific legal rules are encoded.
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


class LegalActionKind(Enum):
    CASE_FILING = "case_filing"
    MOTION = "motion"
    DISCOVERY = "discovery"
    DEPOSITION = "deposition"
    JUDGMENT = "judgment"
    APPEAL = "appeal"
    CONTRACT_REVIEW = "contract_review"
    CONTRACT_EXECUTION = "contract_execution"
    COMPLIANCE_REVIEW = "compliance_review"
    OPINION = "opinion"


@dataclass
class LegalRequest:
    kind: LegalActionKind
    summary: str
    matter_id: str
    lead_counsel: str
    co_counsel: tuple[str, ...] = ()
    client: str = ""
    opposing_party: str = ""  # empty for non-adversarial actions
    jurisdiction: str = ""  # e.g. "US-NY-FED", "EU", "UK"
    court: str = ""  # e.g. "SDNY", "9th Cir." — empty if non-litigation
    bar_admissions_required: tuple[str, ...] = ()  # e.g. ("NY","SDNY")
    privileged: bool = False  # attorney-client / work-product privilege
    acceptance_criteria: tuple[str, ...] = ()
    conflict_flags: tuple[str, ...] = ()  # known COI hits
    is_emergency: bool = False  # TRO, emergency injunction
    statute_deadline_imminent: bool = False
    blast_radius: str = "matter"  # matter | client_portfolio | firm | systemic


@dataclass
class LegalResult:
    case_protocol: tuple[str, ...]
    required_signoffs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    privilege_logged: bool
    is_emergency: bool
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


_LITIGATION_KINDS = (
    LegalActionKind.CASE_FILING,
    LegalActionKind.MOTION,
    LegalActionKind.DISCOVERY,
    LegalActionKind.DEPOSITION,
    LegalActionKind.JUDGMENT,
    LegalActionKind.APPEAL,
)


def translate_to_universal(req: LegalRequest) -> UniversalRequest:
    if req.kind in _LITIGATION_KINDS and not req.court:
        raise ValueError(
            f"litigation action {req.kind.value!r} requires a court "
            "(empty court is only valid for advisory/transactional actions)"
        )

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "legal_state",
        "matter_id": req.matter_id,
        "phase": "pre_action",
        "lead_counsel": req.lead_counsel,
        "client": req.client,
        "opposing_party": req.opposing_party,
    }
    target_state = {
        "kind": "legal_state",
        "matter_id": req.matter_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "privilege_preserved": req.privileged,
    }
    boundary = {
        "inside_predicate": (
            f"matter_id = {req.matter_id} ∧ "
            f"jurisdiction = {req.jurisdiction or '<unspecified>'}"
        ),
        "interface_points": _interface_points(req),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "legal_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]

    # Conflict-of-interest constraints — bar ethics, must block.
    # Even in emergencies, COI remains a block (different from
    # consent in clinical: a lawyer cannot proceed with a known
    # conflict without resolving it).
    for cf in req.conflict_flags:
        constraints.append(
            {
                "domain": "conflict_of_interest",
                "restriction": f"resolve_conflict:{cf}",
                "violation_response": "block",
            }
        )

    # Statute-of-limitations / deadline pressure.
    # Emergency mode escalates instead of blocking (file-now, fix-later).
    if req.statute_deadline_imminent:
        sol_response = "escalate" if req.is_emergency else "block"
        constraints.append(
            {
                "domain": "deadline",
                "restriction": "statute_or_filing_deadline_imminent",
                "violation_response": sol_response,
            }
        )

    # Bar-admission constraint — counsel without required admission
    # cannot appear. Modeled as escalation (pro hac vice path).
    if req.bar_admissions_required:
        constraints.append(
            {
                "domain": "bar_admission",
                "restriction": (
                    "counsel_admitted_or_pro_hac_vice:"
                    + ",".join(req.bar_admissions_required)
                ),
                "violation_response": "escalate",
            }
        )

    # Privileged action without explicit privilege handling — warn.
    # Privilege management is procedural (privilege log exists),
    # not a hard substantive block.
    if req.privileged and req.kind == LegalActionKind.DISCOVERY:
        constraints.append(
            {
                "domain": "privilege",
                "restriction": "privilege_log_filed_with_production",
                "violation_response": "warn",
            }
        )

    authority = (
        f"counsel:{req.lead_counsel}",
    ) + tuple(f"co_counsel:{c}" for c in req.co_counsel)

    observer: tuple[str, ...] = ("matter_audit",)
    if req.jurisdiction:
        observer = observer + (f"jurisdiction:{req.jurisdiction}",)
    if req.court:
        observer = observer + (f"court:{req.court}",)
    for bar in req.bar_admissions_required:
        observer = observer + (f"bar:{bar}",)
    if req.client:
        observer = observer + (f"client:{req.client}",)
    if req.opposing_party:
        observer = observer + (f"opposing:{req.opposing_party}",)
    if req.privileged:
        observer = observer + ("privilege_log",)

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
    original_request: LegalRequest,
) -> LegalResult:
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
        [f"lead: {original_request.lead_counsel}"]
        + [f"co_counsel: {c}" for c in original_request.co_counsel]
    )

    return LegalResult(
        case_protocol=protocol,
        required_signoffs=signoffs,
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        privilege_logged=original_request.privileged,
        is_emergency=original_request.is_emergency,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- run_with_ucja ----


def _request_to_ucja_payload(req: LegalRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "legal_action",
    }


def run_with_ucja(
    req: LegalRequest,
    *,
    capture: list | None = None,
) -> LegalResult:
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
        causation_mechanism="legal_action",
        causation_strength=0.9,
        transformation_energy=1.0,
        transformation_reversibility=_reversibility_for_kind(req.kind),
        validation_evidence_refs=_evidence_refs_for_request(req),
        validation_confidence=0.9,
        observation_sensor="matter_observation",
        observation_signal="filed" if req.kind in _LITIGATION_KINDS else "issued",
        observation_confidence=0.97,
        inference_rule="legal_authority",  # statute, regulation, precedent
        inference_certainty=0.85,
        inference_kind="abductive",  # legal reasoning is best-explanation
        decision_criteria=(
            "acceptance_criteria_satisfied",
            "no_unresolved_conflicts",
        ),
        decision_justification=(
            f"legal action {req.kind.value} for matter {req.matter_id} "
            f"in {req.jurisdiction or 'unspecified jurisdiction'}"
        ),
        execution_plan_prefix=f"execute {req.kind.value} for matter {req.matter_id}",
        execution_resources=tuple(_interface_points(req)),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: LegalActionKind, summary: str) -> str:
    verb_map = {
        LegalActionKind.CASE_FILING:        "initiate_judicial_proceeding",
        LegalActionKind.MOTION:             "petition_court_for_relief",
        LegalActionKind.DISCOVERY:          "compel_or_produce_evidence",
        LegalActionKind.DEPOSITION:         "obtain_sworn_testimony",
        LegalActionKind.JUDGMENT:           "render_dispositive_decision",
        LegalActionKind.APPEAL:             "challenge_lower_court_decision",
        LegalActionKind.CONTRACT_REVIEW:    "evaluate_contractual_instrument",
        LegalActionKind.CONTRACT_EXECUTION: "bind_parties_to_agreement",
        LegalActionKind.COMPLIANCE_REVIEW:  "verify_regulatory_conformance",
        LegalActionKind.OPINION:            "issue_legal_advice",
    }
    return f"{verb_map[kind]}: {summary}"


def _interface_points(req: LegalRequest) -> list[str]:
    points: list[str] = [f"matter:{req.matter_id}"]
    if req.court:
        points.append(f"court:{req.court}")
    if req.client:
        points.append(f"client:{req.client}")
    if req.opposing_party:
        points.append(f"opposing:{req.opposing_party}")
    return points


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "matter":            "closed",
        "client_portfolio":  "selective",
        "firm":              "selective",
        "systemic":          "open",  # precedent-setting
    }.get(blast, "selective")


def _reversibility_for_kind(kind: LegalActionKind) -> str:
    if kind in (
        LegalActionKind.CASE_FILING,
        LegalActionKind.MOTION,
        LegalActionKind.DISCOVERY,
        LegalActionKind.DEPOSITION,
        LegalActionKind.JUDGMENT,
        LegalActionKind.APPEAL,
        LegalActionKind.CONTRACT_EXECUTION,
    ):
        return "irreversible"
    if kind in (
        LegalActionKind.CONTRACT_REVIEW,
        LegalActionKind.COMPLIANCE_REVIEW,
        LegalActionKind.OPINION,
    ):
        return "reversible"
    return "unknown"


def _evidence_refs_for_request(req: LegalRequest) -> tuple[str, ...]:
    refs: list[str] = ["matter_file"]
    if req.kind == LegalActionKind.CONTRACT_REVIEW:
        refs.append("redline_history")
    if req.kind == LegalActionKind.CONTRACT_EXECUTION:
        refs.append("executed_signature_block")
    if req.kind in (LegalActionKind.JUDGMENT, LegalActionKind.APPEAL):
        refs.append("docket_record")
    if req.kind == LegalActionKind.OPINION:
        refs.append("authorities_cited")
    if req.privileged:
        refs.append("privilege_log")
    return tuple(refs)


def _protocol_from_constructs(
    summary: dict[str, int],
    req: LegalRequest,
) -> tuple[str, ...]:
    steps: list[str] = []
    if summary.get("observation", 0) > 0:
        steps.append(f"Capture initial matter state for {req.matter_id}")
    if summary.get("inference", 0) > 0:
        steps.append("Apply governing law and precedent to the action")
    if summary.get("decision", 0) > 0:
        steps.append("Decide whether to proceed with the legal action")
    if summary.get("transformation", 0) > 0:
        steps.append(f"Execute {req.kind.value}")
    if req.conflict_flags:
        steps.append(
            f"Conflicts committee: resolve flags ({', '.join(req.conflict_flags)})"
        )
    for cc in req.co_counsel:
        steps.append(f"Co-counsel signoff: {cc}")
    if req.privileged:
        steps.append("Confirm privilege log entry on file")
    if summary.get("validation", 0) > 0:
        steps.append("Validate work product against acceptance criteria")
    if req.kind == LegalActionKind.CASE_FILING:
        steps.append(f"File complaint with clerk of {req.court or 'court of record'}")
    elif req.kind == LegalActionKind.MOTION:
        steps.append(f"Serve motion on opposing party and file with {req.court or 'court'}")
    elif req.kind == LegalActionKind.JUDGMENT:
        steps.append("Enter judgment on docket and notify parties")
    elif req.kind == LegalActionKind.APPEAL:
        steps.append("Perfect appeal: notice + record + brief")
    elif req.kind == LegalActionKind.CONTRACT_EXECUTION:
        steps.append("Collect executed signature pages and store in contract repository")
    elif req.kind == LegalActionKind.DISCOVERY:
        steps.append("Bates-stamp production set and serve on opposing")
    elif req.kind == LegalActionKind.DEPOSITION:
        steps.append("Reserve court reporter and notice deponent")
    elif req.kind == LegalActionKind.OPINION:
        steps.append("Issue signed legal opinion to client of record")
    if summary.get("execution", 0) > 0:
        steps.append("Persist outcome to matter file and time records")
    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: LegalRequest,
) -> tuple[str, ...]:
    flags: list[str] = []
    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")
    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")
    if result.proof_state == "Unknown":
        flags.append("legal_authority_insufficient")
    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted")

    if req.conflict_flags:
        flags.append(
            f"conflicts_of_interest_present ({', '.join(req.conflict_flags)}) — "
            "conflicts committee must clear before proceeding"
        )
    if req.statute_deadline_imminent:
        flags.append(
            "statute_or_filing_deadline_imminent — verify clock and emergency posture"
        )
    if req.is_emergency:
        flags.append(
            "emergency_mode — file-now-fix-later posture; document justification"
        )
    if (
        req.kind in _LITIGATION_KINDS
        and req.bar_admissions_required
        and not req.co_counsel
    ):
        flags.append(
            f"{req.kind.value}_with_bar_requirements_no_co_counsel — "
            "verify lead admission or pro hac vice"
        )
    if req.blast_radius == "systemic":
        flags.append(
            "systemic_blast_radius — precedent-setting; firm strategy review"
        )
    if req.kind in (
        LegalActionKind.CASE_FILING,
        LegalActionKind.MOTION,
        LegalActionKind.JUDGMENT,
        LegalActionKind.APPEAL,
        LegalActionKind.CONTRACT_EXECUTION,
        LegalActionKind.DEPOSITION,
        LegalActionKind.DISCOVERY,
    ):
        flags.append(
            f"{req.kind.value}_irreversible — confirm before execution"
        )
    if req.privileged and req.kind == LegalActionKind.DISCOVERY:
        flags.append(
            "privileged_discovery — verify privilege log accompanies production"
        )
    if req.kind in _LITIGATION_KINDS and not req.opposing_party:
        flags.append(
            f"{req.kind.value}_without_opposing_party — verify case caption"
        )
    return tuple(flags)
