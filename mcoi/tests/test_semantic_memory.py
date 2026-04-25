"""Purpose: verify semantic memory admission and versioning.
Governance scope: semantic memory write gate tests only.
Invariants:
  - Semantic memory requires admitted learning decisions.
  - Entries carry source and evidence anchors.
  - Supersede appends a new version without mutating old entries.
  - Deferred, rejected, missing, or mismatched admission is rejected.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.knowledge import KnowledgeRecord
from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
from mcoi_runtime.contracts.policy import DecisionReason
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle, PlanningBoundary
from mcoi_runtime.core.semantic_memory import SemanticMemoryStore, semantic_entry_to_planning_knowledge


def _clock():
    counter = [0]

    def now() -> str:
        value = counter[0]
        counter[0] += 1
        return f"2026-04-24T19:00:{value:02d}+00:00"

    return now


def _knowledge(
    knowledge_id: str = "knowledge-semantic-1",
    *,
    content_hash: str = "hash-semantic-1",
    evidence: tuple[EvidenceRecord, ...] | None = None,
) -> KnowledgeRecord:
    return KnowledgeRecord(
        knowledge_id=knowledge_id,
        subject_id="tenant-1",
        content_hash=content_hash,
        evidence=evidence
        if evidence is not None
        else (EvidenceRecord(description="episodic proof", uri="episodic:closure-1"),),
        metadata={"category": "capability_profile"},
    )


def _admission(
    knowledge_id: str = "knowledge-semantic-1",
    *,
    status: LearningAdmissionStatus = LearningAdmissionStatus.ADMIT,
) -> LearningAdmissionDecision:
    return LearningAdmissionDecision(
        admission_id=f"admission-{knowledge_id}-{status.value}",
        knowledge_id=knowledge_id,
        status=status,
        reasons=(DecisionReason(message="semantic memory admission"),),
        issued_at="2026-04-24T19:00:00+00:00",
    )


def test_admits_semantic_memory_with_learning_admission_and_sources():
    store = SemanticMemoryStore(clock=_clock())
    entry = store.admit(
        knowledge=_knowledge(),
        learning_admission=_admission(),
        source_refs=("episodic:closure-1",),
    )

    assert entry.version == 1
    assert entry.knowledge.knowledge_id == "knowledge-semantic-1"
    assert entry.learning_admission_id == "admission-knowledge-semantic-1-admit"
    assert entry.source_refs == ("episodic:closure-1",)
    assert store.current("knowledge-semantic-1") is entry
    assert store.list_versions("knowledge-semantic-1") == (entry,)


def test_projects_current_semantic_entry_into_planning_knowledge():
    store = SemanticMemoryStore(clock=_clock())
    entry = store.admit(
        knowledge=_knowledge(),
        learning_admission=_admission(),
        source_refs=("episodic:closure-1",),
    )
    projected = store.planning_knowledge("knowledge-semantic-1", knowledge_class="capability_profile")

    assert projected is not None
    assert projected.knowledge_id == entry.knowledge.knowledge_id
    assert projected.knowledge_class == "capability_profile"
    assert projected.lifecycle is KnowledgeLifecycle.ADMITTED
    assert projected.admission_id == entry.learning_admission_id
    assert store.planning_knowledge("missing", knowledge_class="capability_profile") is None


def test_projected_semantic_entry_passes_learning_admission_boundary():
    store = SemanticMemoryStore(clock=_clock())
    entry = store.admit(
        knowledge=_knowledge(),
        learning_admission=_admission(),
        source_refs=("episodic:closure-1",),
    )
    projected = semantic_entry_to_planning_knowledge(entry, knowledge_class="capability_profile")
    result = PlanningBoundary().evaluate_with_learning_admission(
        (projected,),
        admitted_classes=("capability_profile",),
        admission_decisions=(_admission(),),
    )

    assert result.admitted == (projected,)
    assert result.rejected == ()
    assert result.admission_decision_ids == (entry.learning_admission_id,)


def test_rejects_semantic_memory_without_evidence():
    store = SemanticMemoryStore(clock=_clock())
    with pytest.raises(RuntimeCoreInvariantError, match="requires evidence"):
        store.admit(
            knowledge=_knowledge(evidence=()),
            learning_admission=_admission(),
            source_refs=("episodic:closure-1",),
        )

    assert store.size == 0
    assert store.current("knowledge-semantic-1") is None
    assert store.list_versions("knowledge-semantic-1") == ()


def test_rejects_non_admitted_learning_decision():
    store = SemanticMemoryStore(clock=_clock())
    with pytest.raises(RuntimeCoreInvariantError, match="admitted learning"):
        store.admit(
            knowledge=_knowledge(),
            learning_admission=_admission(status=LearningAdmissionStatus.DEFER),
            source_refs=("episodic:closure-1",),
        )

    assert store.size == 0
    assert store.current("knowledge-semantic-1") is None
    assert store.list_versions("knowledge-semantic-1") == ()


def test_rejects_learning_admission_for_different_knowledge():
    store = SemanticMemoryStore(clock=_clock())
    with pytest.raises(RuntimeCoreInvariantError, match="knowledge mismatch"):
        store.admit(
            knowledge=_knowledge(),
            learning_admission=_admission("other-knowledge"),
            source_refs=("episodic:closure-1",),
        )

    assert store.size == 0
    assert store.get("missing") is None
    assert store.current("knowledge-semantic-1") is None


def test_supersede_appends_new_version_and_preserves_old_entry():
    store = SemanticMemoryStore(clock=_clock())
    first = store.admit(
        knowledge=_knowledge(),
        learning_admission=_admission(),
        source_refs=("episodic:closure-1",),
    )
    second = store.supersede(
        knowledge=_knowledge(content_hash="hash-semantic-2"),
        learning_admission=_admission(),
        source_refs=("episodic:closure-2",),
        supersedes_entry_id=first.entry_id,
    )

    assert first.version == 1
    assert second.version == 2
    assert second.supersedes_entry_id == first.entry_id
    assert first.knowledge.content_hash == "hash-semantic-1"
    assert store.current("knowledge-semantic-1") is second
    assert store.list_versions("knowledge-semantic-1") == (first, second)


def test_rejects_supersede_that_does_not_target_current_version():
    store = SemanticMemoryStore(clock=_clock())
    first = store.admit(
        knowledge=_knowledge(),
        learning_admission=_admission(),
        source_refs=("episodic:closure-1",),
    )
    second = store.supersede(
        knowledge=_knowledge(content_hash="hash-semantic-2"),
        learning_admission=_admission(),
        source_refs=("episodic:closure-2",),
        supersedes_entry_id=first.entry_id,
    )

    with pytest.raises(RuntimeCoreInvariantError, match="current version"):
        store.supersede(
            knowledge=_knowledge(content_hash="hash-semantic-3"),
            learning_admission=_admission(),
            source_refs=("episodic:closure-3",),
            supersedes_entry_id=first.entry_id,
        )

    assert store.size == 2
    assert store.current("knowledge-semantic-1") is second
    assert store.list_versions("knowledge-semantic-1") == (first, second)
