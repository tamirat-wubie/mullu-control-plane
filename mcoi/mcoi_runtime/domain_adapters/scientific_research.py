"""
Scientific Research Domain Adapter.

Translates research workflows (hypothesis testing, experiment design,
peer review, replication) into the universal causal framework.

The shape that distinguishes this adapter from `software_dev` and
`business_process`:

  - Authority comes from peer review, not tenant role
  - Validation requires evidence with explicit confidence (p-value,
    effect size, replication count)
  - Reversibility is a function of replication state — irreversible
    only when retraction is a peer-review event itself
  - Acceptance criteria include statistical thresholds, not yes/no checks

This adapter demonstrates that the 25-construct framework reaches a third
domain shape distinct from the prior two — not just renaming.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from mcoi_runtime.domain_adapters.software_dev import (
    UniversalRequest,
    UniversalResult,
)


class ResearchActionKind(Enum):
    HYPOTHESIS_FORMATION = "hypothesis_formation"
    EXPERIMENT_DESIGN = "experiment_design"
    DATA_COLLECTION = "data_collection"
    ANALYSIS = "analysis"
    PEER_REVIEW = "peer_review"
    PUBLICATION = "publication"
    REPLICATION = "replication"
    RETRACTION = "retraction"


@dataclass
class ResearchRequest:
    """Domain-shaped input from a researcher."""

    kind: ResearchActionKind
    summary: str
    study_id: str
    principal_investigator: str
    peer_reviewers: tuple[str, ...] = ()
    affected_corpus: tuple[str, ...] = ()  # datasets, prior studies
    acceptance_criteria: tuple[str, ...] = ()
    confidence_threshold: float = 0.95  # 1 - p-value threshold
    minimum_replications: int = 1
    statistical_power_target: float = 0.8
    blast_radius: str = "study"  # study | subfield | field | discipline


@dataclass
class ResearchResult:
    """Domain-shaped output."""

    research_protocol: tuple[str, ...]
    required_reviewers: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    confidence_threshold: float
    minimum_replications: int
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


def translate_to_universal(req: ResearchRequest) -> UniversalRequest:
    """Project research request into universal causal shape.

    Mapping:
      - kind                       → purpose_statement
      - study_id                   → boundary.inside_predicate
      - peer_reviewers             → authority_required + observer_required
      - affected_corpus            → boundary.interface_points
      - acceptance_criteria        → constraint_set (block-level)
      - confidence_threshold       → constraint (statistical, escalate)
      - minimum_replications       → constraint (replication, escalate)
      - statistical_power_target   → constraint (power, warn)
      - blast_radius               → boundary.permeability hint
    """
    if not (0.0 < req.confidence_threshold <= 1.0):
        raise ValueError("confidence_threshold must be in (0, 1]")
    if req.minimum_replications < 0:
        raise ValueError("minimum_replications must be non-negative")
    if not (0.0 < req.statistical_power_target <= 1.0):
        raise ValueError("statistical_power_target must be in (0, 1]")

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "research_state",
        "study_id": req.study_id,
        "phase": "pre_action",
        "principal_investigator": req.principal_investigator,
        "corpus": list(req.affected_corpus),
    }

    target_state = {
        "kind": "research_state",
        "study_id": req.study_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "confidence_threshold": req.confidence_threshold,
        "minimum_replications": req.minimum_replications,
    }

    boundary = {
        "inside_predicate": (
            f"study_id = {req.study_id} ∧ "
            f"corpus ⊆ {{{', '.join(req.affected_corpus)}}}"
        ),
        "interface_points": list(req.affected_corpus),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "research_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]
    # Statistical constraints — distinct from acceptance criteria
    constraints.append(
        {
            "domain": "statistical_significance",
            "restriction": (
                f"reject_null_at_alpha_{1.0 - req.confidence_threshold:.4f}"
            ),
            "violation_response": "escalate",
        }
    )
    if req.minimum_replications > 0:
        constraints.append(
            {
                "domain": "replication",
                "restriction": (
                    f"replications_completed >= {req.minimum_replications}"
                ),
                "violation_response": "escalate",
            }
        )
    constraints.append(
        {
            "domain": "statistical_power",
            "restriction": f"power >= {req.statistical_power_target}",
            "violation_response": "warn",
        }
    )

    # Authority comes from peer reviewers; PI alone is insufficient
    if req.peer_reviewers:
        authority = tuple(f"peer_reviewer:{r}" for r in req.peer_reviewers)
    else:
        authority = (f"principal_investigator:{req.principal_investigator}",)
    observer = (
        ("peer_review_committee",)
        if req.peer_reviewers
        else ("study_audit_log",)
    )

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
    original_request: ResearchRequest,
) -> ResearchResult:
    """Project universal result back into research-shaped output."""
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

    return ResearchResult(
        research_protocol=protocol,
        required_reviewers=tuple(original_request.peer_reviewers),
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        confidence_threshold=original_request.confidence_threshold,
        minimum_replications=original_request.minimum_replications,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- End-to-end: UCJA → SCCCE ----


def _request_to_ucja_payload(req: ResearchRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "research_action",
    }


def run_with_ucja(
    req: ResearchRequest,
    *,
    capture: list | None = None,
) -> ResearchResult:
    """Full pipeline: ResearchRequest → UCJA → SCCCE → ResearchResult.

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
        causation_mechanism="research_action",
        causation_strength=req.confidence_threshold,
        transformation_energy=float(req.minimum_replications),
        # Retraction is the only research action structurally irreversible.
        transformation_reversibility=(
            "irreversible"
            if req.kind == ResearchActionKind.RETRACTION
            else "reversible"
        ),
        validation_evidence_refs=("peer_review_signoff", "statistical_test_passed"),
        validation_confidence=req.confidence_threshold,
        observation_sensor="experimental_data",
        observation_signal=req.kind.value,
        observation_confidence=req.confidence_threshold,
        inference_rule="statistical_inference",
        inference_certainty=req.confidence_threshold,
        inference_kind="inductive",
        decision_criteria=(
            "peer_review_consensus",
            "statistical_significance",
        ),
        decision_justification=(
            f"peer review consensus + p-value below "
            f"{1.0 - req.confidence_threshold:.4f}"
        ),
        execution_plan_prefix=f"execute {req.kind.value}",
        execution_resources=tuple(req.affected_corpus),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: ResearchActionKind, summary: str) -> str:
    verb_map = {
        ResearchActionKind.HYPOTHESIS_FORMATION: "formulate_testable_proposition",
        ResearchActionKind.EXPERIMENT_DESIGN:    "specify_falsifiable_protocol",
        ResearchActionKind.DATA_COLLECTION:      "acquire_observational_evidence",
        ResearchActionKind.ANALYSIS:             "extract_inference_from_evidence",
        ResearchActionKind.PEER_REVIEW:          "validate_via_external_authority",
        ResearchActionKind.PUBLICATION:          "publish_validated_finding",
        ResearchActionKind.REPLICATION:          "verify_via_independent_repetition",
        ResearchActionKind.RETRACTION:           "withdraw_published_finding",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "study":      "closed",
        "subfield":   "selective",
        "field":      "selective",
        "discipline": "open",
    }.get(blast, "selective")


def _protocol_from_constructs(
    summary: dict[str, int],
    req: ResearchRequest,
) -> tuple[str, ...]:
    steps: list[str] = []

    if summary.get("observation", 0) > 0:
        steps.append(
            f"Capture initial state of study {req.study_id}"
        )

    if summary.get("inference", 0) > 0:
        steps.append(
            f"Apply statistical inference at α={1.0 - req.confidence_threshold:.4f}"
        )

    if summary.get("decision", 0) > 0:
        steps.append("Decide accept/reject hypothesis")

    if summary.get("transformation", 0) > 0:
        steps.append(
            f"Apply {req.kind.value} action to corpus "
            f"({len(req.affected_corpus)} item(s))"
        )

    if req.peer_reviewers:
        for reviewer in req.peer_reviewers:
            steps.append(f"Submit for peer review: {reviewer}")

    if summary.get("validation", 0) > 0:
        steps.append(
            f"Validate replications complete (≥ {req.minimum_replications})"
        )

    if req.kind == ResearchActionKind.PUBLICATION:
        steps.append("Issue DOI and archive in study registry")
    elif req.kind == ResearchActionKind.RETRACTION:
        steps.append("Mark publication as retracted in registry")
    elif req.kind == ResearchActionKind.REPLICATION:
        steps.append("Compare replicated results to original within tolerance")

    if summary.get("execution", 0) > 0:
        steps.append("Persist research outcome to study log")

    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: ResearchRequest,
) -> tuple[str, ...]:
    flags: list[str] = []

    if result.rejected_deltas:
        flags.append(
            f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov"
        )

    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")

    if result.proof_state == "Unknown":
        flags.append("evidence_insufficient — gather more data before proceeding")

    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted — escalate")

    if req.minimum_replications == 0:
        flags.append(
            "no_replications_required — single-study finding cannot be confirmed"
        )

    if req.confidence_threshold < 0.95:
        flags.append(
            f"low_confidence_threshold ({req.confidence_threshold:.2f}) — "
            "below conventional 0.95"
        )

    if req.statistical_power_target < 0.8:
        flags.append(
            f"underpowered_study ({req.statistical_power_target:.2f}) — "
            "type II error risk elevated"
        )

    if req.blast_radius == "discipline":
        flags.append(
            "discipline_blast_radius — coordinate with discipline-wide review"
        )

    if req.kind == ResearchActionKind.RETRACTION:
        flags.append("retraction — irreversible; ensure cause is documented")

    if not req.peer_reviewers and req.kind in (
        ResearchActionKind.PUBLICATION,
        ResearchActionKind.RETRACTION,
    ):
        flags.append(
            f"no_peer_reviewers — {req.kind.value} without external authority "
            "is not validated research"
        )

    return tuple(flags)
