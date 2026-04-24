"""Purpose: tests for terminal-closure learning admission.
Governance scope: episodic-to-learning admission decisions for effect-bearing
command closures.
Invariants:
  - Committed and compensated trusted closures may be admitted.
  - Accepted-risk closure is deferred.
  - Review-required closure is rejected.
  - Certificates must bind the episodic memory entry being evaluated.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.learning import LearningAdmissionStatus
from mcoi_runtime.contracts.terminal_closure import TerminalClosureCertificate, TerminalClosureDisposition
from mcoi_runtime.core.closure_learning import ClosureLearningAdmissionGate
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import MemoryEntry, MemoryTier


NOW = "2026-04-24T17:00:00+00:00"


def _clock():
    counter = [0]

    def now() -> str:
        value = counter[0]
        counter[0] += 1
        return f"2026-04-24T17:00:{value:02d}+00:00"

    return now


def _certificate(
    disposition: TerminalClosureDisposition,
    *,
    memory_entry_id: str = "episodic-learning-1",
) -> TerminalClosureCertificate:
    return TerminalClosureCertificate(
        certificate_id=f"cert-learning-{disposition.value}",
        command_id="cmd-learning-1",
        execution_id="exec-learning-1",
        disposition=disposition,
        verification_result_id="ver-learning-1",
        effect_reconciliation_id="recon-learning-1",
        evidence_refs=("evidence:learning-1",),
        closed_at=NOW,
        memory_entry_id=memory_entry_id,
        compensation_outcome_id="comp-outcome-learning-1"
        if disposition is TerminalClosureDisposition.COMPENSATED
        else None,
        accepted_risk_id="risk-learning-1" if disposition is TerminalClosureDisposition.ACCEPTED_RISK else None,
        case_id="case-learning-1"
        if disposition
        in (TerminalClosureDisposition.ACCEPTED_RISK, TerminalClosureDisposition.REQUIRES_REVIEW)
        else None,
    )


def _execution_memory(
    *,
    entry_id: str = "episodic-learning-1",
    category: str = "execution_success",
    trust_class: str = "trusted",
    execution_id: str = "exec-learning-1",
) -> MemoryEntry:
    return MemoryEntry(
        entry_id=entry_id,
        tier=MemoryTier.EPISODIC,
        category=category,
        content={
            "trust_class": trust_class,
            "execution_id": execution_id,
            "evidence_refs": ("evidence:learning-1",),
        },
        source_ids=("exec-learning-1", "ver-learning-1"),
    )


def _compensation_memory() -> MemoryEntry:
    return MemoryEntry(
        entry_id="episodic-learning-1",
        tier=MemoryTier.EPISODIC,
        category="compensation_success",
        content={
            "trust_class": "trusted_compensation",
            "command_id": "cmd-learning-1",
            "evidence_refs": ("refund:receipt-1",),
        },
        source_ids=("comp-outcome-learning-1", "ver-comp-learning-1", "recon-comp-learning-1"),
    )


def test_admits_committed_terminal_closure_from_trusted_episodic_memory():
    gate = ClosureLearningAdmissionGate(clock=_clock())
    decision = gate.decide(
        certificate=_certificate(TerminalClosureDisposition.COMMITTED),
        memory_entry=_execution_memory(),
        learning_scope="semantic",
        proposed_use="capability performance profile",
    )
    assert decision.status is LearningAdmissionStatus.ADMIT
    assert decision.metadata["terminal_disposition"] == "committed"
    assert decision.metadata["trust_class"] == "trusted"
    assert gate.get_decision(decision.admission_id) is decision


def test_admits_compensated_terminal_closure_from_trusted_compensation_memory():
    gate = ClosureLearningAdmissionGate(clock=_clock())
    decision = gate.decide(
        certificate=_certificate(TerminalClosureDisposition.COMPENSATED),
        memory_entry=_compensation_memory(),
        learning_scope="procedural",
        proposed_use="compensation runbook candidate",
    )
    assert decision.status is LearningAdmissionStatus.ADMIT
    assert decision.reasons[0].code == "terminal_closure.compensated_admitted"
    assert decision.metadata["memory_category"] == "compensation_success"
    assert decision.knowledge_id.startswith("closure-knowledge-")


def test_defers_accepted_risk_terminal_closure_from_planning_use():
    gate = ClosureLearningAdmissionGate(clock=_clock())
    decision = gate.decide(
        certificate=_certificate(TerminalClosureDisposition.ACCEPTED_RISK),
        memory_entry=_execution_memory(category="execution_accepted_risk", trust_class="accepted_risk"),
        learning_scope="semantic",
        proposed_use="provider reliability pattern",
    )
    assert decision.status is LearningAdmissionStatus.DEFER
    assert decision.reasons[0].code == "terminal_closure.accepted_risk_deferred"
    assert decision.metadata["terminal_disposition"] == "accepted_risk"
    assert gate.decision_count == 1


def test_rejects_review_required_terminal_closure_from_planning_use():
    gate = ClosureLearningAdmissionGate(clock=_clock())
    decision = gate.decide(
        certificate=_certificate(TerminalClosureDisposition.REQUIRES_REVIEW),
        memory_entry=_execution_memory(category="execution_failure", trust_class="failure_record"),
        learning_scope="semantic",
        proposed_use="provider reliability pattern",
    )
    assert decision.status is LearningAdmissionStatus.REJECT
    assert decision.reasons[0].code == "terminal_closure.review_rejected"
    assert decision.metadata["memory_category"] == "execution_failure"
    assert decision.metadata["trust_class"] == "failure_record"


def test_rejects_committed_closure_when_memory_execution_does_not_match():
    gate = ClosureLearningAdmissionGate(clock=_clock())
    decision = gate.decide(
        certificate=_certificate(TerminalClosureDisposition.COMMITTED),
        memory_entry=_execution_memory(execution_id="exec-other"),
        learning_scope="semantic",
        proposed_use="capability performance profile",
    )
    assert decision.status is LearningAdmissionStatus.REJECT
    assert decision.reasons[0].code == "terminal_closure.execution_mismatch"
    assert decision.metadata["terminal_certificate_id"] == "cert-learning-committed"
    assert gate.decision_count == 1


def test_requires_certificate_to_bind_the_same_memory_entry():
    gate = ClosureLearningAdmissionGate(clock=_clock())
    with pytest.raises(RuntimeCoreInvariantError, match="memory entry mismatch"):
        gate.decide(
            certificate=_certificate(TerminalClosureDisposition.COMMITTED, memory_entry_id="episodic-other"),
            memory_entry=_execution_memory(),
            learning_scope="semantic",
            proposed_use="capability performance profile",
        )
    assert gate.decision_count == 0
    assert gate.get_decision("missing") is None
    assert _execution_memory().entry_id == "episodic-learning-1"
