"""Purpose: verify planning input admission rules for runtime-core.
Governance scope: runtime-core tests only.
Dependencies: the runtime-core planning boundary module.
Invariants: inadmissible knowledge is rejected with explicit reasons and never filtered silently.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
from mcoi_runtime.contracts.policy import DecisionReason
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.planning_boundary import (
    KnowledgeLifecycle,
    PlanningBoundary,
    PlanningKnowledge,
    PlanningRejectionReason,
)


def test_planning_boundary_rejects_inadmissible_knowledge_explicitly() -> None:
    boundary = PlanningBoundary()
    result = boundary.evaluate(
        (
            PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
            PlanningKnowledge("knowledge-2", "constraint", KnowledgeLifecycle.CANDIDATE),
            PlanningKnowledge("knowledge-3", "constraint", KnowledgeLifecycle.BLOCKED),
            PlanningKnowledge("knowledge-4", "constraint", KnowledgeLifecycle.DEPRECATED),
            PlanningKnowledge("knowledge-5", "reference", KnowledgeLifecycle.ADMITTED),
        ),
        admitted_classes=("constraint",),
    )

    rejection_map = {item.knowledge_id: item.reason for item in result.rejected}

    assert tuple(item.knowledge_id for item in result.admitted) == ("knowledge-1",)
    assert rejection_map["knowledge-2"] is PlanningRejectionReason.CANDIDATE_KNOWLEDGE
    assert rejection_map["knowledge-3"] is PlanningRejectionReason.BLOCKED_KNOWLEDGE
    assert rejection_map["knowledge-4"] is PlanningRejectionReason.DEPRECATED_KNOWLEDGE
    assert rejection_map["knowledge-5"] is PlanningRejectionReason.UNAPPROVED_CLASS


def _admission(
    knowledge_id: str = "knowledge-1",
    status: LearningAdmissionStatus = LearningAdmissionStatus.ADMIT,
) -> LearningAdmissionDecision:
    return LearningAdmissionDecision(
        admission_id=f"admission-{knowledge_id}-{status.value}",
        knowledge_id=knowledge_id,
        status=status,
        reasons=(DecisionReason(message="learning admission test reason"),),
        issued_at="2026-04-24T18:00:00+00:00",
    )


def test_planning_boundary_requires_learning_admission_for_proof_mode() -> None:
    boundary = PlanningBoundary()
    result = boundary.evaluate_with_learning_admission(
        (
            PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
            PlanningKnowledge("knowledge-2", "constraint", KnowledgeLifecycle.ADMITTED),
            PlanningKnowledge("knowledge-3", "constraint", KnowledgeLifecycle.CANDIDATE),
        ),
        admitted_classes=("constraint",),
        admission_decisions=(_admission("knowledge-1"),),
    )

    rejection_map = {item.knowledge_id: item.reason for item in result.rejected}

    assert tuple(item.knowledge_id for item in result.admitted) == ("knowledge-1",)
    assert result.admission_decision_ids == ("admission-knowledge-1-admit",)
    assert rejection_map["knowledge-2"] is PlanningRejectionReason.MISSING_ADMISSION_DECISION
    assert rejection_map["knowledge-3"] is PlanningRejectionReason.CANDIDATE_KNOWLEDGE


def test_planning_boundary_rejects_deferred_or_rejected_learning_decisions() -> None:
    boundary = PlanningBoundary()
    result = boundary.evaluate_with_learning_admission(
        (
            PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
            PlanningKnowledge("knowledge-2", "constraint", KnowledgeLifecycle.ADMITTED),
        ),
        admitted_classes=("constraint",),
        admission_decisions=(
            _admission("knowledge-1", LearningAdmissionStatus.DEFER),
            _admission("knowledge-2", LearningAdmissionStatus.REJECT),
        ),
    )

    rejection_map = {item.knowledge_id: item.reason for item in result.rejected}

    assert result.admitted == ()
    assert result.admission_decision_ids == ()
    assert rejection_map["knowledge-1"] is PlanningRejectionReason.NON_ADMITTED_LEARNING_DECISION
    assert rejection_map["knowledge-2"] is PlanningRejectionReason.NON_ADMITTED_LEARNING_DECISION


def test_planning_boundary_verifies_referenced_admission_id() -> None:
    boundary = PlanningBoundary()
    result = boundary.evaluate_with_learning_admission(
        (
            PlanningKnowledge(
                "knowledge-1",
                "constraint",
                KnowledgeLifecycle.ADMITTED,
                admission_id="admission-other",
            ),
        ),
        admitted_classes=("constraint",),
        admission_decisions=(_admission("knowledge-1"),),
    )

    assert result.admitted == ()
    assert result.rejected[0].knowledge_id == "knowledge-1"
    assert result.rejected[0].reason is PlanningRejectionReason.NON_ADMITTED_LEARNING_DECISION
    assert result.rejected[0].message == "planning knowledge references a different admission decision"


def test_planning_boundary_rejects_duplicate_admission_decisions() -> None:
    boundary = PlanningBoundary()
    with pytest.raises(RuntimeCoreInvariantError, match="duplicate learning admission"):
        boundary.evaluate_with_learning_admission(
            (PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),),
            admitted_classes=("constraint",),
            admission_decisions=(_admission("knowledge-1"), _admission("knowledge-1")),
        )

    assert boundary.evaluate((), admitted_classes=("constraint",)).admitted == ()
    assert boundary.evaluate((), admitted_classes=("constraint",)).rejected == ()
    assert boundary.evaluate((), admitted_classes=("constraint",)).admission_decision_ids == ()
