"""Purpose: wire runtime-core boundaries without adapter behavior.
Governance scope: runtime-core coordination only.
Dependencies: registry, evidence, planning, policy, and replay core modules.
Invariants: kernel stays explicit, small, and free of execution adapter logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic

from mcoi_runtime.contracts.learning import LearningAdmissionDecision

from .evidence_merger import EvidenceInput, EvidenceMerger, EvidenceState
from .planning_boundary import PlanningBoundary, PlanningBoundaryResult, PlanningKnowledge
from .policy_engine import DecisionT, PolicyDecisionFactory, PolicyEngine, PolicyInput
from .registry_index import RegistryIndex, RegistryIndexSnapshot
from .registry_store import EntryT, RegistryEntry, RegistryStore
from .replay_engine import ReplayEngine, ReplayRecord, ReplayValidationResult


@dataclass(slots=True)
class RuntimeKernel(Generic[EntryT, DecisionT]):
    registry_store: RegistryStore[EntryT]
    registry_index: RegistryIndex[EntryT]
    evidence_merger: EvidenceMerger
    planning_boundary: PlanningBoundary
    policy_engine: PolicyEngine[DecisionT]
    replay_engine: ReplayEngine

    def register(self, entry: RegistryEntry[EntryT]) -> RegistryEntry[EntryT]:
        stored_entry = self.registry_store.add(entry)
        self.registry_index.refresh(self.registry_store)
        return stored_entry

    def refresh_index(self) -> RegistryIndexSnapshot:
        return self.registry_index.refresh(self.registry_store)

    def merge_evidence(
        self,
        state: EvidenceState,
        evidence_entries: tuple[EvidenceInput, ...],
    ) -> EvidenceState:
        return self.evidence_merger.merge(state, evidence_entries)

    def evaluate_planning(
        self,
        knowledge_entries: tuple[PlanningKnowledge, ...],
        admitted_classes: tuple[str, ...],
    ) -> PlanningBoundaryResult:
        return self.planning_boundary.evaluate(knowledge_entries, admitted_classes)

    def evaluate_planning_with_learning_admission(
        self,
        knowledge_entries: tuple[PlanningKnowledge, ...],
        admitted_classes: tuple[str, ...],
        admission_decisions: tuple[LearningAdmissionDecision, ...],
    ) -> PlanningBoundaryResult:
        return self.planning_boundary.evaluate_with_learning_admission(
            knowledge_entries,
            admitted_classes,
            admission_decisions,
        )

    def evaluate_policy(
        self,
        policy_input: PolicyInput,
        decision_factory: PolicyDecisionFactory[DecisionT],
    ) -> DecisionT:
        return self.policy_engine.evaluate(policy_input, decision_factory)

    def validate_replay(self, replay_record: ReplayRecord) -> ReplayValidationResult:
        return self.replay_engine.validate(replay_record)
