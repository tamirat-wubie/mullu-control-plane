"""
Construction / AEC Domain Adapter.

Translates construction project actions (permit application, RFI, change
order, submittal review, inspection, milestone, lien waiver, punch list,
substantial completion, project close-out) into the universal causal
framework. Distinct shape:

  - Authority chain: project manager + approver chain (general
    contractor superintendent + engineer-of-record). The PERMIT
    AUTHORITY (building department), inspectors, and safety officer
    (OSHA-equivalent) are observer-shaped — they witness and can
    block via separate channels (stop-work orders), but they do not
    authorize project actions.
  - Constraints carry acceptance criteria, permit-on-file (block),
    safety-incident-frozen (active OSHA stop-work blocks routine
    work), trades-coordinated (multi-trade conflict resolution), and
    weather/site-condition exposure — each with different
    violation_response.
  - The ``active_safety_incident`` flag inverts the usual logic for
    INSPECTION and INCIDENT_RESPONSE-like actions (those proceed
    during the freeze; everything else blocks unless emergency
    repair).
  - Many actions are physically irreversible once executed
    (POUR / structural commits beneath SUBSTANTIAL_COMPLETION,
    LIEN_WAIVER once signed, CLOSEOUT, CHANGE_ORDER once executed).
    Submittals, RFIs, inspections, and punch list items remain
    reversible.
  - Risk flags surface missing permits, active safety incidents,
    multi-trade conflicts, weather exposure, and project-portfolio
    blast radius (precedent).

This adapter intentionally does NOT model schedule / cost / earned
value or codify specific building codes — it models the governance
shape, and leaves jurisdiction-specific rules (IBC, NEC, NFPA,
local amendments, OSHA 29 CFR 1926) to the calling system.
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


class ConstructionActionKind(Enum):
    PERMIT_APPLICATION = "permit_application"
    RFI = "rfi"  # request for information
    CHANGE_ORDER = "change_order"
    SUBMITTAL_REVIEW = "submittal_review"
    INSPECTION = "inspection"
    MILESTONE = "milestone"  # e.g. foundation pour, dry-in
    LIEN_WAIVER = "lien_waiver"
    PUNCH_LIST = "punch_list"
    SUBSTANTIAL_COMPLETION = "substantial_completion"
    CLOSEOUT = "closeout"


_VALID_TRADES = frozenset({
    "general", "structural", "civil", "mep_mechanical", "mep_electrical",
    "mep_plumbing", "envelope", "interior_finishes", "site_work",
    "specialty",
})


@dataclass
class ConstructionRequest:
    kind: ConstructionActionKind
    summary: str
    project_id: str
    project_manager: str
    approver_chain: tuple[str, ...] = ()
    general_contractor: str = ""
    owner: str = ""
    permit_authority: str = ""  # e.g. "DBI-SF", "NYC-DOB"
    jurisdiction: str = ""
    trades_involved: tuple[str, ...] = ()  # subset of _VALID_TRADES
    affected_drawings: tuple[str, ...] = ()  # e.g. ("S-101","M-203")
    acceptance_criteria: tuple[str, ...] = ()
    permit_on_file: bool = False
    permit_required: bool = True
    active_safety_incident: bool = False
    multi_trade_coordinated: bool = True  # trades have signed coord doc
    weather_sensitive: bool = False  # exposed pour, lift, etc.
    weather_window_open: bool = True  # forecast supports the operation
    is_emergency: bool = False  # emergency repair / make-safe
    blast_radius: str = "task"  # task | floor | building | project_portfolio


@dataclass
class ConstructionResult:
    project_protocol: tuple[str, ...]
    required_signoffs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    permit_on_file: bool
    active_safety_incident: bool
    is_emergency: bool
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


_PHYSICAL_KINDS = (
    ConstructionActionKind.MILESTONE,
    ConstructionActionKind.CHANGE_ORDER,
    ConstructionActionKind.SUBSTANTIAL_COMPLETION,
)

_INSPECTION_LIKE_KINDS = (
    ConstructionActionKind.INSPECTION,
    ConstructionActionKind.PUNCH_LIST,
)


def translate_to_universal(req: ConstructionRequest) -> UniversalRequest:
    bad_trades = [t for t in req.trades_involved if t not in _VALID_TRADES]
    if bad_trades:
        raise ValueError(
            f"unknown trade(s) {bad_trades!r}; valid: {sorted(_VALID_TRADES)}"
        )
    if (
        req.kind == ConstructionActionKind.PERMIT_APPLICATION
        and not req.permit_authority
    ):
        raise ValueError(
            f"permit_application requires permit_authority "
            f"(project_id={req.project_id})"
        )

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "construction_state",
        "project_id": req.project_id,
        "phase": "pre_action",
        "project_manager": req.project_manager,
        "general_contractor": req.general_contractor,
        "trades": list(req.trades_involved),
    }
    target_state = {
        "kind": "construction_state",
        "project_id": req.project_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "permit_on_file": req.permit_on_file,
    }
    boundary = {
        "inside_predicate": (
            f"project_id = {req.project_id} ∧ "
            f"drawings ⊆ {{{', '.join(req.affected_drawings)}}}"
        ),
        "interface_points": list(req.affected_drawings),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "construction_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]

    # Permit on file — physical-commit kinds may not proceed without
    # a permit on file. Permit application itself is the obvious
    # exception (you can't have a permit before applying).
    if (
        req.permit_required
        and not req.permit_on_file
        and req.kind != ConstructionActionKind.PERMIT_APPLICATION
    ):
        # Emergency make-safe is the narrow exception per most
        # jurisdictions — relax to escalate.
        permit_response = "escalate" if req.is_emergency else "block"
        constraints.append(
            {
                "domain": "permit",
                "restriction": "permit_on_file_before_work",
                "violation_response": permit_response,
            }
        )

    # Active safety incident — invert the usual logic. Inspection-
    # like and emergency-response-shaped kinds proceed (they ARE the
    # response). Routine work blocks unless emergency repair.
    if (
        req.active_safety_incident
        and req.kind not in _INSPECTION_LIKE_KINDS
    ):
        sf_response = "escalate" if req.is_emergency else "block"
        constraints.append(
            {
                "domain": "safety_freeze",
                "restriction": "no_routine_work_during_active_incident",
                "violation_response": sf_response,
            }
        )

    # Multi-trade coordination — when more than one trade is involved,
    # the coordination document must be signed. Block until done;
    # this is how clashes (HVAC vs. structural beam, e.g.) get caught
    # before steel goes in. Single-trade actions skip this check.
    if (
        len(req.trades_involved) > 1
        and not req.multi_trade_coordinated
    ):
        constraints.append(
            {
                "domain": "trade_coordination",
                "restriction": "multi_trade_coordination_signed",
                "violation_response": "block",
            }
        )

    # Weather-sensitive operations (concrete pour, crane lift,
    # roofing) must have a favorable forecast window. Escalate
    # rather than block — the field decision is risk-weighted.
    if req.weather_sensitive and not req.weather_window_open:
        constraints.append(
            {
                "domain": "weather",
                "restriction": "favorable_weather_window",
                "violation_response": "escalate",
            }
        )

    authority = (
        f"pm:{req.project_manager}",
    ) + tuple(f"approver:{a}" for a in req.approver_chain)

    observer: tuple[str, ...] = ("project_audit",)
    if req.general_contractor:
        observer = observer + (f"gc:{req.general_contractor}",)
    if req.owner:
        observer = observer + (f"owner:{req.owner}",)
    if req.permit_authority:
        observer = observer + (f"permit_authority:{req.permit_authority}",)
    if req.jurisdiction:
        observer = observer + (f"jurisdiction:{req.jurisdiction}",)
    for trade in req.trades_involved:
        observer = observer + (f"trade:{trade}",)
    # OSHA-shape safety officer is recorded on every action — site
    # safety oversight is a continuous observer in modern AEC
    # practice.
    observer = observer + ("safety_officer",)
    if req.active_safety_incident:
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
    original_request: ConstructionRequest,
) -> ConstructionResult:
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
        [f"pm: {original_request.project_manager}"]
        + [f"approver: {a}" for a in original_request.approver_chain]
    )

    return ConstructionResult(
        project_protocol=protocol,
        required_signoffs=signoffs,
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        permit_on_file=original_request.permit_on_file,
        active_safety_incident=original_request.active_safety_incident,
        is_emergency=original_request.is_emergency,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- run_with_ucja ----


def _request_to_ucja_payload(req: ConstructionRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "construction_action",
    }


def run_with_ucja(
    req: ConstructionRequest,
    *,
    capture: list | None = None,
) -> ConstructionResult:
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
        causation_mechanism="construction_action",
        causation_strength=0.92,
        transformation_energy=1.0,
        transformation_reversibility=_reversibility_for_kind(req.kind),
        validation_evidence_refs=_evidence_refs_for_request(req),
        validation_confidence=0.94,
        observation_sensor="site_observation",
        observation_signal="recorded",
        observation_confidence=0.96,
        inference_rule="contract_documents_or_code",
        inference_certainty=0.9,
        inference_kind="deductive",  # specs and code apply mechanically
        decision_criteria=(
            "acceptance_criteria_satisfied",
            "permit_on_file_or_application",
            "no_active_safety_freeze",
        ),
        decision_justification=(
            f"construction action {req.kind.value} for project {req.project_id} "
            f"({req.permit_authority or 'unspecified authority'})"
        ),
        execution_plan_prefix=f"execute {req.kind.value} for project {req.project_id}",
        execution_resources=tuple(req.affected_drawings),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: ConstructionActionKind, summary: str) -> str:
    verb_map = {
        ConstructionActionKind.PERMIT_APPLICATION:    "petition_authority_for_permit",
        ConstructionActionKind.RFI:                   "request_clarification_from_design",
        ConstructionActionKind.CHANGE_ORDER:          "modify_contract_scope_or_price",
        ConstructionActionKind.SUBMITTAL_REVIEW:      "verify_product_meets_specification",
        ConstructionActionKind.INSPECTION:            "verify_completed_work_in_place",
        ConstructionActionKind.MILESTONE:             "commit_physical_milestone",
        ConstructionActionKind.LIEN_WAIVER:           "release_lien_rights_for_payment",
        ConstructionActionKind.PUNCH_LIST:            "track_remaining_completion_items",
        ConstructionActionKind.SUBSTANTIAL_COMPLETION:"transfer_beneficial_use_to_owner",
        ConstructionActionKind.CLOSEOUT:              "complete_project_administratively",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "task":                "closed",
        "floor":               "selective",
        "building":            "selective",
        "project_portfolio":   "open",
    }.get(blast, "selective")


def _reversibility_for_kind(kind: ConstructionActionKind) -> str:
    if kind in (
        ConstructionActionKind.MILESTONE,  # physical pour, etc.
        ConstructionActionKind.CHANGE_ORDER,  # contractually binding
        ConstructionActionKind.LIEN_WAIVER,  # rights waived
        ConstructionActionKind.SUBSTANTIAL_COMPLETION,  # beneficial use
        ConstructionActionKind.CLOSEOUT,  # admin close
    ):
        return "irreversible"
    if kind in (
        ConstructionActionKind.PERMIT_APPLICATION,
        ConstructionActionKind.RFI,
        ConstructionActionKind.SUBMITTAL_REVIEW,
        ConstructionActionKind.INSPECTION,
        ConstructionActionKind.PUNCH_LIST,
    ):
        return "reversible"
    return "unknown"


def _evidence_refs_for_request(req: ConstructionRequest) -> tuple[str, ...]:
    refs: list[str] = ["project_record"]
    if req.permit_on_file:
        refs.append("permit_on_file")
    if req.kind == ConstructionActionKind.SUBMITTAL_REVIEW:
        refs.append("submittal_package")
    if req.kind == ConstructionActionKind.INSPECTION:
        refs.append("inspection_report")
    if req.kind == ConstructionActionKind.CHANGE_ORDER:
        refs.append("price_and_schedule_impact")
    if req.kind == ConstructionActionKind.LIEN_WAIVER:
        refs.append("payment_evidence")
    if req.kind == ConstructionActionKind.SUBSTANTIAL_COMPLETION:
        refs.append("certificate_of_occupancy_or_eq")
    if req.multi_trade_coordinated and len(req.trades_involved) > 1:
        refs.append("trade_coordination_signoff")
    if req.weather_sensitive:
        refs.append("weather_forecast_record")
    return tuple(refs)


def _protocol_from_constructs(
    summary: dict[str, int],
    req: ConstructionRequest,
) -> tuple[str, ...]:
    steps: list[str] = []
    if summary.get("observation", 0) > 0:
        steps.append(f"Capture initial state for project {req.project_id}")
    if summary.get("inference", 0) > 0:
        steps.append("Apply contract documents and applicable code")
    if summary.get("decision", 0) > 0:
        steps.append("Decide on construction action")
    if summary.get("transformation", 0) > 0:
        steps.append(f"Execute {req.kind.value}")
    if (
        req.permit_required
        and req.kind != ConstructionActionKind.PERMIT_APPLICATION
    ):
        if req.permit_on_file:
            steps.append(
                f"Confirm permit on file with {req.permit_authority or 'authority'}"
            )
        elif req.is_emergency:
            steps.append(
                "Emergency make-safe — document factual predicate and "
                "notify authority post-action"
            )
        else:
            steps.append("Block: permit not on file")
    if req.active_safety_incident:
        if req.kind in _INSPECTION_LIKE_KINDS:
            steps.append(
                "Active safety incident — proceed with inspection-shape action"
            )
        elif req.is_emergency:
            steps.append(
                "Emergency repair under active incident — escalate to safety officer"
            )
        else:
            steps.append("Block: routine work attempted during active safety incident")
    if len(req.trades_involved) > 1:
        if req.multi_trade_coordinated:
            steps.append(
                f"Confirm trade coordination signoff "
                f"({', '.join(req.trades_involved)})"
            )
        else:
            steps.append(
                f"Block: multi-trade coordination unsigned "
                f"({', '.join(req.trades_involved)})"
            )
    if req.weather_sensitive:
        if req.weather_window_open:
            steps.append("Confirm weather window open and forecast favorable")
        else:
            steps.append("Escalate weather decision to PM and superintendent")
    for a in req.approver_chain:
        steps.append(f"Approver signoff: {a}")
    if summary.get("validation", 0) > 0:
        steps.append("Validate against acceptance criteria")
    if req.kind == ConstructionActionKind.PERMIT_APPLICATION:
        steps.append(
            f"File permit application with {req.permit_authority or 'authority'}"
        )
    elif req.kind == ConstructionActionKind.RFI:
        steps.append("Issue RFI to design team and track response time")
    elif req.kind == ConstructionActionKind.CHANGE_ORDER:
        steps.append(
            "Issue change order with price and schedule impact recorded"
        )
    elif req.kind == ConstructionActionKind.MILESTONE:
        steps.append(
            "Execute physical milestone and record evidence (photos, surveys)"
        )
    elif req.kind == ConstructionActionKind.LIEN_WAIVER:
        steps.append("Collect signed lien waiver in exchange for payment")
    elif req.kind == ConstructionActionKind.SUBSTANTIAL_COMPLETION:
        steps.append(
            "Issue certificate of substantial completion and start warranty"
        )
    elif req.kind == ConstructionActionKind.CLOSEOUT:
        steps.append(
            "Deliver O&M manuals, as-builts, and final lien waivers"
        )
    if summary.get("execution", 0) > 0:
        steps.append("Persist event to project record and daily log")
    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: ConstructionRequest,
) -> tuple[str, ...]:
    flags: list[str] = []
    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")
    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")
    if result.proof_state == "Unknown":
        flags.append("contract_or_code_evidence_insufficient")
    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted")

    if (
        req.permit_required
        and not req.permit_on_file
        and req.kind != ConstructionActionKind.PERMIT_APPLICATION
    ):
        if req.is_emergency:
            flags.append(
                "permit_missing_under_emergency — make-safe path; "
                "document predicate and notify authority"
            )
        else:
            flags.append(
                "permit_missing_routine_work — block until permit on file"
            )
    if req.active_safety_incident:
        if req.kind in _INSPECTION_LIKE_KINDS:
            flags.append(
                f"active_safety_incident_during_{req.kind.value} — "
                "verify inspection scope covers incident"
            )
        else:
            flags.append(
                f"active_safety_incident_with_{req.kind.value} — "
                f"{'emergency repair path' if req.is_emergency else 'block until cleared'}"
            )
    if (
        len(req.trades_involved) > 1
        and not req.multi_trade_coordinated
    ):
        flags.append(
            f"multi_trade_uncoordinated ({', '.join(req.trades_involved)}) — "
            "block until coordination signed"
        )
    if req.weather_sensitive and not req.weather_window_open:
        flags.append(
            "weather_window_unfavorable — escalate go/no-go to "
            "superintendent"
        )
    if req.is_emergency:
        flags.append(
            "emergency_make_safe_posture — document predicate"
        )
    if req.blast_radius == "project_portfolio":
        flags.append(
            "project_portfolio_blast_radius — affects multiple projects; "
            "engage program management"
        )
    if req.kind in (
        ConstructionActionKind.MILESTONE,
        ConstructionActionKind.CHANGE_ORDER,
        ConstructionActionKind.LIEN_WAIVER,
        ConstructionActionKind.SUBSTANTIAL_COMPLETION,
        ConstructionActionKind.CLOSEOUT,
    ):
        flags.append(
            f"{req.kind.value}_irreversible — confirm before execution"
        )
    if (
        req.kind == ConstructionActionKind.PERMIT_APPLICATION
        and not req.affected_drawings
    ):
        flags.append(
            "permit_application_without_drawing_set — verify scope"
        )
    return tuple(flags)
