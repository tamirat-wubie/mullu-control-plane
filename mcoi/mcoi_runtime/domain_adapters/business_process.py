"""
Business Process Domain Adapter.

Translates business workflow shapes (approvals, escalations, SLA tasks)
into the universal causal framework. Pattern matches `software_dev`:

  - translate_to_universal(request) -> UniversalRequest
  - translate_from_universal(result, original) -> BusinessResult
  - run_with_ucja(request) -> BusinessResult  (full UCJA → SCCCE round trip)

Business processes have richer authority/approval semantics than software
work, so this adapter populates `authority_required` from the approval
chain rather than from a generic role list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

# Reuse the universal request/result shapes from software_dev — domain
# adapters are independent but the universal types are domain-neutral.
from mcoi_runtime.domain_adapters.software_dev import (
    UniversalRequest,
    UniversalResult,
)


class BusinessActionKind(Enum):
    APPROVAL = "approval"
    ESCALATION = "escalation"
    SLA_TASK = "sla_task"
    PROCUREMENT = "procurement"
    ONBOARDING = "onboarding"
    OFFBOARDING = "offboarding"
    POLICY_CHANGE = "policy_change"


@dataclass
class BusinessRequest:
    """Domain-shaped input from a process operator."""

    kind: BusinessActionKind
    summary: str
    process_id: str
    initiator: str
    approval_chain: tuple[str, ...] = ()
    sla_deadline_hours: float | None = None
    affected_systems: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    dollar_impact: float = 0.0  # >=0
    blast_radius: str = "department"  # team | department | division | enterprise


@dataclass
class BusinessResult:
    """Domain-shaped output."""

    workflow_steps: tuple[str, ...]
    required_approvals: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    governance_status: str
    audit_trail_id: UUID
    sla_deadline_hours: float | None = None


# ---- Translation ----


def translate_to_universal(req: BusinessRequest) -> UniversalRequest:
    """Project business request into universal causal shape.

    Mapping:
      - kind                → purpose_statement (verb + object)
      - process_id          → boundary.inside_predicate
      - approval_chain      → authority_required + observer_required
      - sla_deadline_hours  → constraint with timing restriction
      - affected_systems    → boundary.interface_points
      - acceptance_criteria → constraint_set
      - dollar_impact       → blast_radius hint
      - blast_radius        → boundary.permeability hint
    """
    if req.dollar_impact < 0:
        raise ValueError("dollar_impact must be non-negative")

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "business_state",
        "process_id": req.process_id,
        "initiator": req.initiator,
        "phase": "pre_action",
        "affected_systems": list(req.affected_systems),
    }

    target_state = {
        "kind": "business_state",
        "process_id": req.process_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
    }

    boundary = {
        "inside_predicate": (
            f"process_id = {req.process_id} ∧ "
            f"systems ⊆ {{{', '.join(req.affected_systems)}}}"
        ),
        "interface_points": list(req.affected_systems),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "business_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]
    if req.sla_deadline_hours is not None:
        if req.sla_deadline_hours <= 0:
            raise ValueError("sla_deadline_hours must be positive when set")
        constraints.append(
            {
                "domain": "sla",
                "restriction": f"completion_within_{req.sla_deadline_hours}h",
                "violation_response": "escalate",
            }
        )

    # Approval chain populates authority + observer roles
    if req.approval_chain:
        authority = tuple(f"approver:{a}" for a in req.approval_chain)
        observer = ("approval_recorder",)
    else:
        # No approval chain → the initiator is sole authority
        authority = (f"initiator:{req.initiator}",)
        observer = ("audit_log",)

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
    original_request: BusinessRequest,
) -> BusinessResult:
    """Project universal result back into business-shaped output."""
    workflow_steps = _workflow_steps_from_constructs(
        universal_result.construct_graph_summary,
        original_request,
    )

    risk_flags = _risk_flags_from_result(universal_result, original_request)

    governance_status = (
        "approved"
        if universal_result.proof_state == "Pass"
        else f"blocked: {universal_result.proof_state}"
    )

    return BusinessResult(
        workflow_steps=workflow_steps,
        required_approvals=tuple(original_request.approval_chain),
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
        sla_deadline_hours=original_request.sla_deadline_hours,
    )


# ---- End-to-end: UCJA → SCCCE ----


def _request_to_ucja_payload(req: BusinessRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "business_action",
    }


def run_with_ucja(
    req: BusinessRequest,
    *,
    capture: list | None = None,
) -> BusinessResult:
    """Full pipeline: BusinessRequest → UCJA → SCCCE → BusinessResult.

    Migrated to use `_cycle_helpers.run_default_cycle` in v4.8.0.
    """
    from mcoi_runtime.domain_adapters._cycle_helpers import (
        StepOverrides,
        run_default_cycle,
    )
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
        causation_mechanism="business_action",
        causation_strength=0.9,
        transformation_energy=req.dollar_impact,
        transformation_reversibility=(
            "irreversible"
            if req.kind in {
                BusinessActionKind.OFFBOARDING,
                BusinessActionKind.PROCUREMENT,
            }
            else "reversible"
        ),
        validation_evidence_refs=("approval_recorded",),
        validation_confidence=0.95,
        observation_sensor="approval_log",
        observation_signal="approved",
        observation_confidence=0.99,
        inference_rule="business_policy",
        inference_certainty=0.9,
        inference_kind="deductive",
        decision_criteria=("policy_compliance",),
        decision_justification="all approval chain checks passed",
        execution_plan_prefix=f"execute {req.kind.value}",
        execution_resources=tuple(req.affected_systems),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: BusinessActionKind, summary: str) -> str:
    verb_map = {
        BusinessActionKind.APPROVAL:      "issue_authoritative_approval",
        BusinessActionKind.ESCALATION:    "escalate_for_higher_authority_review",
        BusinessActionKind.SLA_TASK:      "complete_within_service_level",
        BusinessActionKind.PROCUREMENT:   "acquire_external_resource",
        BusinessActionKind.ONBOARDING:    "introduce_actor_to_system",
        BusinessActionKind.OFFBOARDING:   "remove_actor_from_system",
        BusinessActionKind.POLICY_CHANGE: "modify_governing_constraint",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "team":       "closed",
        "department": "selective",
        "division":   "selective",
        "enterprise": "open",
    }.get(blast, "selective")


def _workflow_steps_from_constructs(
    summary: dict[str, int],
    req: BusinessRequest,
) -> tuple[str, ...]:
    steps: list[str] = []

    if summary.get("observation", 0) > 0:
        steps.append(f"Capture initial state of process {req.process_id}")

    if summary.get("inference", 0) > 0:
        steps.append("Apply business policy to derive required action")

    if summary.get("decision", 0) > 0:
        steps.append("Decide approval/rejection per policy")

    if summary.get("transformation", 0) > 0:
        steps.append(f"Apply {req.kind.value} action within process boundary")

    if req.approval_chain:
        for approver in req.approval_chain:
            steps.append(f"Route to approver: {approver}")

    if summary.get("validation", 0) > 0:
        steps.append("Record approval and validate completion criteria")

    if req.sla_deadline_hours is not None:
        steps.append(f"Track against SLA: {req.sla_deadline_hours}h")

    if summary.get("execution", 0) > 0:
        steps.append("Persist outcome to audit log")

    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult, req: BusinessRequest
) -> tuple[str, ...]:
    flags: list[str] = []

    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")

    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")

    if result.proof_state == "Unknown":
        flags.append("evidence_insufficient — gather more before proceeding")

    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted — escalate")

    if req.dollar_impact >= 100_000:
        flags.append(
            f"high_dollar_impact ({req.dollar_impact:.0f}) — require dual approval"
        )

    if req.blast_radius == "enterprise":
        flags.append("enterprise_blast_radius — broadcast change announcement required")

    if (
        req.sla_deadline_hours is not None
        and req.sla_deadline_hours < 4
    ):
        flags.append("tight_sla — escalation path must be pre-armed")

    return tuple(flags)
