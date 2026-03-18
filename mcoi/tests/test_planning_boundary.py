"""Purpose: verify planning input admission rules for runtime-core.
Governance scope: runtime-core tests only.
Dependencies: the runtime-core planning boundary module.
Invariants: inadmissible knowledge is rejected with explicit reasons and never filtered silently.
"""

from __future__ import annotations

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
