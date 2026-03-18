"""Purpose: reject inadmissible knowledge before planning.
Governance scope: runtime-core planning input admission only.
Dependencies: runtime-core invariant helpers.
Invariants: candidate, blocked, deprecated, and unapproved knowledge never cross the planning boundary silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

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


@dataclass(frozen=True, slots=True)
class PlanningKnowledge:
    knowledge_id: str
    knowledge_class: str
    lifecycle: KnowledgeLifecycle

    def __post_init__(self) -> None:
        object.__setattr__(self, "knowledge_id", ensure_non_empty_text("knowledge_id", self.knowledge_id))
        object.__setattr__(self, "knowledge_class", ensure_non_empty_text("knowledge_class", self.knowledge_class))
        if not isinstance(self.lifecycle, KnowledgeLifecycle):
            raise RuntimeCoreInvariantError("lifecycle must be a KnowledgeLifecycle value")


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
