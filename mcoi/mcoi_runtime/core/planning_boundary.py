"""Purpose: reject inadmissible knowledge before planning.
Governance scope: runtime-core planning input admission only.
Dependencies: learning admission contracts and runtime-core invariant helpers.
Invariants: candidate, blocked, deprecated, unapproved, and unadmitted
knowledge never cross the planning boundary silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text


class KnowledgeLifecycle(StrEnum):
    ADMITTED = "admitted"
    CANDIDATE = "candidate"
    BLOCKED = "blocked"
    DEPRECATED = "deprecated"


class PlanningRejectionReason(StrEnum):
    CANDIDATE_KNOWLEDGE = "candidate_knowledge"
    BLOCKED_KNOWLEDGE = "blocked_knowledge"
    DEPRECATED_KNOWLEDGE = "deprecated_knowledge"
    UNAPPROVED_CLASS = "unapproved_class"
    MISSING_ADMISSION_DECISION = "missing_admission_decision"
    NON_ADMITTED_LEARNING_DECISION = "non_admitted_learning_decision"


@dataclass(frozen=True, slots=True)
class PlanningKnowledge:
    knowledge_id: str
    knowledge_class: str
    lifecycle: KnowledgeLifecycle
    admission_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "knowledge_id", ensure_non_empty_text("knowledge_id", self.knowledge_id))
        object.__setattr__(self, "knowledge_class", ensure_non_empty_text("knowledge_class", self.knowledge_class))
        if not isinstance(self.lifecycle, KnowledgeLifecycle):
            raise RuntimeCoreInvariantError("lifecycle must be a KnowledgeLifecycle value")
        if self.admission_id is not None:
            object.__setattr__(self, "admission_id", ensure_non_empty_text("admission_id", self.admission_id))


@dataclass(frozen=True, slots=True)
class PlanningRejection:
    knowledge_id: str
    reason: PlanningRejectionReason
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "knowledge_id", ensure_non_empty_text("knowledge_id", self.knowledge_id))
        if not isinstance(self.reason, PlanningRejectionReason):
            raise RuntimeCoreInvariantError("reason must be a PlanningRejectionReason value")
        object.__setattr__(self, "message", ensure_non_empty_text("message", self.message))


@dataclass(frozen=True, slots=True)
class PlanningBoundaryResult:
    admitted: tuple[PlanningKnowledge, ...]
    rejected: tuple[PlanningRejection, ...]
    admission_decision_ids: tuple[str, ...] = ()


class PlanningBoundary:
    """Deterministic knowledge gate for planning inputs."""

    def evaluate(
        self,
        knowledge_entries: tuple[PlanningKnowledge, ...],
        admitted_classes: tuple[str, ...],
    ) -> PlanningBoundaryResult:
        allowed_classes = tuple(sorted(ensure_non_empty_text("knowledge_class", value) for value in admitted_classes))
        admitted: list[PlanningKnowledge] = []
        rejected: list[PlanningRejection] = []

        for knowledge in knowledge_entries:
            if knowledge.lifecycle is KnowledgeLifecycle.CANDIDATE:
                rejected.append(
                    PlanningRejection(
                        knowledge_id=knowledge.knowledge_id,
                        reason=PlanningRejectionReason.CANDIDATE_KNOWLEDGE,
                        message="candidate knowledge cannot enter planning",
                    )
                )
                continue
            if knowledge.lifecycle is KnowledgeLifecycle.BLOCKED:
                rejected.append(
                    PlanningRejection(
                        knowledge_id=knowledge.knowledge_id,
                        reason=PlanningRejectionReason.BLOCKED_KNOWLEDGE,
                        message="blocked knowledge cannot enter planning",
                    )
                )
                continue
            if knowledge.lifecycle is KnowledgeLifecycle.DEPRECATED:
                rejected.append(
                    PlanningRejection(
                        knowledge_id=knowledge.knowledge_id,
                        reason=PlanningRejectionReason.DEPRECATED_KNOWLEDGE,
                        message="deprecated knowledge cannot enter planning",
                    )
                )
                continue
            if knowledge.knowledge_class not in allowed_classes:
                rejected.append(
                    PlanningRejection(
                        knowledge_id=knowledge.knowledge_id,
                        reason=PlanningRejectionReason.UNAPPROVED_CLASS,
                        message="knowledge class is not admitted for planning",
                    )
                )
                continue
            admitted.append(knowledge)

        return PlanningBoundaryResult(admitted=tuple(admitted), rejected=tuple(rejected))

    def evaluate_with_learning_admission(
        self,
        knowledge_entries: tuple[PlanningKnowledge, ...],
        admitted_classes: tuple[str, ...],
        admission_decisions: tuple[LearningAdmissionDecision, ...],
    ) -> PlanningBoundaryResult:
        """Evaluate planning inputs with explicit learning admission proof."""
        decision_by_knowledge = _index_admission_decisions(admission_decisions)
        preliminary = self.evaluate(knowledge_entries, admitted_classes)
        admitted: list[PlanningKnowledge] = []
        rejected: list[PlanningRejection] = list(preliminary.rejected)
        admitted_decision_ids: list[str] = []

        for knowledge in preliminary.admitted:
            decision = decision_by_knowledge.get(knowledge.knowledge_id)
            if decision is None:
                rejected.append(
                    PlanningRejection(
                        knowledge_id=knowledge.knowledge_id,
                        reason=PlanningRejectionReason.MISSING_ADMISSION_DECISION,
                        message="planning knowledge requires a learning admission decision",
                    )
                )
                continue
            if knowledge.admission_id is not None and knowledge.admission_id != decision.admission_id:
                rejected.append(
                    PlanningRejection(
                        knowledge_id=knowledge.knowledge_id,
                        reason=PlanningRejectionReason.NON_ADMITTED_LEARNING_DECISION,
                        message="planning knowledge references a different admission decision",
                    )
                )
                continue
            if decision.status is not LearningAdmissionStatus.ADMIT:
                rejected.append(
                    PlanningRejection(
                        knowledge_id=knowledge.knowledge_id,
                        reason=PlanningRejectionReason.NON_ADMITTED_LEARNING_DECISION,
                        message="learning admission decision does not admit planning use",
                    )
                )
                continue
            admitted.append(knowledge)
            admitted_decision_ids.append(decision.admission_id)

        return PlanningBoundaryResult(
            admitted=tuple(admitted),
            rejected=tuple(rejected),
            admission_decision_ids=tuple(admitted_decision_ids),
        )


def _index_admission_decisions(
    admission_decisions: tuple[LearningAdmissionDecision, ...],
) -> dict[str, LearningAdmissionDecision]:
    indexed: dict[str, LearningAdmissionDecision] = {}
    for decision in admission_decisions:
        if not isinstance(decision.status, LearningAdmissionStatus):
            raise RuntimeCoreInvariantError("admission decision status must be a LearningAdmissionStatus value")
        if decision.knowledge_id in indexed:
            raise RuntimeCoreInvariantError("duplicate learning admission decision for knowledge")
        indexed[decision.knowledge_id] = decision
    return indexed
