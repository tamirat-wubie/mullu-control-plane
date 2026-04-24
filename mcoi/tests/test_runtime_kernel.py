"""Purpose: verify runtime-kernel boundary wiring for runtime-core.
Governance scope: runtime-core tests only.
Dependencies: the runtime-core modules only.
Invariants: kernel coordinates boundaries without absorbing adapter or execution logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
from mcoi_runtime.contracts.policy import DecisionReason
from mcoi_runtime.core.evidence_merger import EvidenceInput, EvidenceMerger, EvidenceState, EvidenceStateCategory
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle, PlanningBoundary, PlanningKnowledge
from mcoi_runtime.core.policy_engine import PolicyEngine, PolicyInput, PolicyReason
from mcoi_runtime.core.registry_index import RegistryIndex
from mcoi_runtime.core.registry_store import RegistryEntry, RegistryLifecycle, RegistryStore
from mcoi_runtime.core.replay_engine import (
    EffectControl,
    ReplayArtifact,
    ReplayEffect,
    ReplayEngine,
    ReplayMode,
    ReplayRecord,
)
from mcoi_runtime.core.runtime_kernel import RuntimeKernel


@dataclass(slots=True)
class CapabilityRecord:
    capability_id: str


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    decision_id: str
    subject_id: str
    goal_id: str
    status: str
    reasons: tuple[PolicyReason, ...]
    issued_at: str


def build_decision(**kwargs: object) -> PolicyDecision:
    return PolicyDecision(**kwargs)


def test_runtime_kernel_wires_core_boundaries_without_adapter_logic() -> None:
    kernel: RuntimeKernel[CapabilityRecord, PolicyDecision] = RuntimeKernel(
        registry_store=RegistryStore(),
        registry_index=RegistryIndex(),
        evidence_merger=EvidenceMerger(),
        planning_boundary=PlanningBoundary(),
        policy_engine=PolicyEngine(),
        replay_engine=ReplayEngine(),
    )

    kernel.register(
        RegistryEntry(
            entry_id="capability-1",
            entry_type="capability",
            value=CapabilityRecord(capability_id="cap-1"),
            lifecycle=RegistryLifecycle.ACTIVE,
        )
    )
    merged_state = kernel.merge_evidence(
        EvidenceState(),
        (
            EvidenceInput(
                evidence_id="evidence-1",
                state_key="workspace.files",
                value=12,
                category=EvidenceStateCategory.OBSERVED,
            ),
        ),
    )
    planning_result = kernel.evaluate_planning(
        (
            PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
        ),
        admitted_classes=("constraint",),
    )
    admission_result = kernel.evaluate_planning_with_learning_admission(
        (
            PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
        ),
        admitted_classes=("constraint",),
        admission_decisions=(
            LearningAdmissionDecision(
                admission_id="admission-1",
                knowledge_id="knowledge-1",
                status=LearningAdmissionStatus.ADMIT,
                reasons=(DecisionReason(message="admitted knowledge only"),),
                issued_at="2026-03-18T12:00:00+00:00",
            ),
        ),
    )
    policy_decision = kernel.evaluate_policy(
        PolicyInput(
            subject_id="subject-1",
            goal_id="goal-1",
            issued_at="2026-03-18T12:00:00+00:00",
        ),
        build_decision,
    )
    replay_result = kernel.validate_replay(
        ReplayRecord(
            replay_id="replay-1",
            trace_id="trace-1",
            source_hash="source-1",
            approved_effects=(
                ReplayEffect(
                    effect_id="effect-1",
                    control=EffectControl.CONTROLLED,
                    artifact_id="artifact-1",
                ),
            ),
            blocked_effects=(),
            mode=ReplayMode.OBSERVATION_ONLY,
            recorded_at="2026-03-18T12:00:00+00:00",
            artifacts=(ReplayArtifact(artifact_id="artifact-1", payload_digest="digest-1"),),
        )
    )

    assert kernel.registry_index.ids_for_type("capability") == ("capability-1",)
    assert merged_state.observed["workspace.files"].provenance_ids == ("evidence-1",)
    assert tuple(item.knowledge_id for item in planning_result.admitted) == ("knowledge-1",)
    assert admission_result.admission_decision_ids == ("admission-1",)
    assert policy_decision.status == "allow"
    assert replay_result.ready is True
