"""
Education Domain Adapter.

Translates instructional and credentialing workflows (course offering,
assessment, grading, certification) into the universal causal framework.
Distinct shape:

  - Authority chain: instructor + (optional) curriculum committee +
    accreditation body for certifications.
  - Constraints carry prerequisite chains, accessibility (ADA)
    requirements, assessment validity.
  - Most actions reversible (grades can be appealed; courses can be
    withdrawn). CERTIFICATION and ACCREDITATION are irreversible at the
    framework level (they're issued events; revocation is its own action).
  - Risk flags surface prerequisite-not-met, accessibility violations,
    accreditation scope mismatches, and certification scope drift.
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


class EducationActionKind(Enum):
    COURSE_OFFERING = "course_offering"
    ENROLLMENT = "enrollment"
    ASSESSMENT_DESIGN = "assessment_design"
    GRADING = "grading"
    GRADE_APPEAL = "grade_appeal"
    CERTIFICATION = "certification"
    ACCREDITATION = "accreditation"
    WITHDRAWAL = "withdrawal"


@dataclass
class EducationRequest:
    kind: EducationActionKind
    summary: str
    course_id: str
    instructor: str
    curriculum_committee: tuple[str, ...] = ()
    accreditation_body: str = ""
    affected_learners: tuple[str, ...] = ()
    learning_objectives: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    prerequisite_courses: tuple[str, ...] = ()
    accessibility_requirements: tuple[str, ...] = ()
    blast_radius: str = "course"  # course | program | department | institution


@dataclass
class EducationResult:
    instructional_protocol: tuple[str, ...]
    required_signoffs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    learning_objectives: tuple[str, ...]
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


def translate_to_universal(req: EducationRequest) -> UniversalRequest:
    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "instructional_state",
        "course_id": req.course_id,
        "phase": "pre_action",
        "instructor": req.instructor,
        "learners": list(req.affected_learners),
    }
    target_state = {
        "kind": "instructional_state",
        "course_id": req.course_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "learning_objectives_completed": list(req.learning_objectives),
    }
    boundary = {
        "inside_predicate": (
            f"course_id = {req.course_id} ∧ "
            f"learners ⊆ {{{', '.join(req.affected_learners)}}}"
        ),
        "interface_points": list(req.affected_learners),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "instructional_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]

    # Prerequisite checks — escalate (registrar may override)
    for prereq in req.prerequisite_courses:
        constraints.append(
            {
                "domain": "prerequisite",
                "restriction": f"completed:{prereq}",
                "violation_response": "escalate",
            }
        )

    # Accessibility — block (legal requirement, not optional)
    for access in req.accessibility_requirements:
        constraints.append(
            {
                "domain": "accessibility",
                "restriction": f"satisfies:{access}",
                "violation_response": "block",
            }
        )

    # Learning objectives — warn if some target objectives are unstated
    if req.learning_objectives:
        constraints.append(
            {
                "domain": "learning_objectives",
                "restriction": (
                    f"all_objectives_assessed:{len(req.learning_objectives)}"
                ),
                "violation_response": "warn",
            }
        )

    # Authority chain
    authority: tuple[str, ...] = (f"instructor:{req.instructor}",)
    if req.curriculum_committee:
        authority = authority + tuple(
            f"committee:{c}" for c in req.curriculum_committee
        )
    if req.accreditation_body and req.kind in (
        EducationActionKind.CERTIFICATION,
        EducationActionKind.ACCREDITATION,
    ):
        authority = authority + (f"accreditor:{req.accreditation_body}",)

    observer = ("registrar_audit",) + tuple(
        f"learner:{ln}" for ln in req.affected_learners[:3]
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
    original_request: EducationRequest,
) -> EducationResult:
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

    signoffs: list[str] = [f"instructor: {original_request.instructor}"]
    for c in original_request.curriculum_committee:
        signoffs.append(f"committee: {c}")
    if original_request.accreditation_body:
        signoffs.append(f"accreditor: {original_request.accreditation_body}")

    return EducationResult(
        instructional_protocol=protocol,
        required_signoffs=tuple(signoffs),
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        learning_objectives=tuple(original_request.learning_objectives),
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- run_with_ucja ----


def _request_to_ucja_payload(req: EducationRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "instructional_action",
    }


def run_with_ucja(
    req: EducationRequest,
    *,
    capture: list | None = None,
) -> EducationResult:
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
        causation_mechanism="instructional_action",
        causation_strength=0.9,
        transformation_energy=float(len(req.affected_learners) or 1),
        transformation_reversibility=_reversibility_for_kind(req.kind),
        validation_evidence_refs=("assessment_results", "rubric_signoff"),
        validation_confidence=0.9,
        observation_sensor="learning_management_system",
        observation_signal="objectives_met",
        observation_confidence=0.95,
        inference_rule="learning_outcome_inference",
        inference_certainty=0.85,
        inference_kind="inductive",
        decision_criteria=("learning_objectives_met", "prerequisites_satisfied"),
        decision_justification=(
            f"objectives complete and prerequisites satisfied for "
            f"{len(req.affected_learners)} learner(s)"
        ),
        execution_plan_prefix=f"execute {req.kind.value} for course {req.course_id}",
        execution_resources=tuple(req.affected_learners),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: EducationActionKind, summary: str) -> str:
    verb_map = {
        EducationActionKind.COURSE_OFFERING:   "offer_instructional_module",
        EducationActionKind.ENROLLMENT:        "register_learner_in_module",
        EducationActionKind.ASSESSMENT_DESIGN: "construct_evaluation_instrument",
        EducationActionKind.GRADING:           "evaluate_learner_performance",
        EducationActionKind.GRADE_APPEAL:      "review_disputed_evaluation",
        EducationActionKind.CERTIFICATION:     "attest_learner_competence",
        EducationActionKind.ACCREDITATION:     "validate_program_against_standard",
        EducationActionKind.WITHDRAWAL:        "remove_learner_from_module",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "course":      "closed",
        "program":     "selective",
        "department":  "selective",
        "institution": "open",
    }.get(blast, "selective")


def _reversibility_for_kind(kind: EducationActionKind) -> str:
    if kind in (
        EducationActionKind.CERTIFICATION,
        EducationActionKind.ACCREDITATION,
    ):
        return "irreversible"
    if kind in (
        EducationActionKind.GRADING,
        EducationActionKind.WITHDRAWAL,
        EducationActionKind.GRADE_APPEAL,
    ):
        return "reversible"
    return "unknown"


def _protocol_from_constructs(
    summary: dict[str, int],
    req: EducationRequest,
) -> tuple[str, ...]:
    steps: list[str] = []
    if summary.get("observation", 0) > 0:
        steps.append(f"Capture initial state for course {req.course_id}")
    if summary.get("inference", 0) > 0:
        steps.append("Infer learning outcomes from current evidence")
    if summary.get("decision", 0) > 0:
        steps.append("Decide pass/fail/needs-improvement per rubric")
    if summary.get("transformation", 0) > 0:
        steps.append(f"Execute {req.kind.value} for {len(req.affected_learners)} learner(s)")
    for prereq in req.prerequisite_courses:
        steps.append(f"Verify prerequisite: {prereq}")
    for access in req.accessibility_requirements:
        steps.append(f"Verify accessibility: {access}")
    for member in req.curriculum_committee:
        steps.append(f"Route to curriculum committee: {member}")
    if req.accreditation_body and req.kind in (
        EducationActionKind.CERTIFICATION,
        EducationActionKind.ACCREDITATION,
    ):
        steps.append(f"Submit to accreditor: {req.accreditation_body}")
    if summary.get("validation", 0) > 0:
        steps.append("Validate outcome against learning objectives")
    if req.kind == EducationActionKind.CERTIFICATION:
        steps.append("Issue credential and record in learner transcript")
    elif req.kind == EducationActionKind.GRADE_APPEAL:
        steps.append("Document appeal outcome in registrar record")
    if summary.get("execution", 0) > 0:
        steps.append("Persist outcome to learning management system")
    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: EducationRequest,
) -> tuple[str, ...]:
    flags: list[str] = []
    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")
    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")
    if result.proof_state == "Unknown":
        flags.append("assessment_evidence_insufficient")
    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted")

    if (
        req.kind == EducationActionKind.ENROLLMENT
        and not req.prerequisite_courses
        and req.affected_learners
    ):
        flags.append(
            "no_prerequisites_declared — verify policy doesn't require them"
        )
    if not req.accessibility_requirements and req.affected_learners:
        flags.append(
            "no_accessibility_requirements_declared — ADA/equivalent compliance unverified"
        )
    if not req.learning_objectives and req.kind in (
        EducationActionKind.COURSE_OFFERING,
        EducationActionKind.ASSESSMENT_DESIGN,
        EducationActionKind.CERTIFICATION,
    ):
        flags.append(
            f"{req.kind.value}_without_learning_objectives — outcome not measurable"
        )
    if (
        req.kind == EducationActionKind.CERTIFICATION
        and not req.accreditation_body
    ):
        flags.append(
            "certification_without_accreditor — credential validity limited"
        )
    if req.blast_radius == "institution":
        flags.append("institution_blast_radius — coordinate with senior leadership")
    if req.kind in (
        EducationActionKind.CERTIFICATION,
        EducationActionKind.ACCREDITATION,
    ):
        flags.append(
            f"{req.kind.value}_irreversible — revocation is a separate event"
        )
    return tuple(flags)
