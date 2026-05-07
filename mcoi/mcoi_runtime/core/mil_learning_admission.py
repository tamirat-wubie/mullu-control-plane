"""Purpose: admit terminally certified MIL outcomes into learning memory.
Governance scope: only closed MIL outcomes with terminal certificates may become episodic memory anchors.
Dependencies: learning contracts, memory core, terminal closure contracts, and MIL terminal certificate bundles.
Invariants: no uncertified execution result is retained; review-required closures defer learning admission.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
from mcoi_runtime.contracts.policy import DecisionReason
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.memory import EpisodicMemory, MemoryEntry, MemoryTier
from mcoi_runtime.core.mil_terminal_certificate import MILTerminalCertificateBundle


@dataclass(frozen=True, slots=True)
class MILLearningAdmissionResult:
    decision: LearningAdmissionDecision
    memory_entry: MemoryEntry | None


def admit_mil_terminal_learning(
    bundle: MILTerminalCertificateBundle,
    episodic: EpisodicMemory,
    *,
    issued_at: str,
) -> MILLearningAdmissionResult:
    _validate_bundle(bundle)
    knowledge_id = f"mil-terminal:{bundle.certificate.certificate_id}"

    if bundle.certificate.disposition is not TerminalClosureDisposition.COMMITTED:
        decision = LearningAdmissionDecision(
            _admission_id(knowledge_id, issued_at),
            knowledge_id,
            LearningAdmissionStatus.DEFER,
            (DecisionReason("terminal closure is not committed", "mil_learning_defer"),),
            issued_at,
            metadata={"disposition": bundle.certificate.disposition.value},
        )
        return MILLearningAdmissionResult(decision, None)

    entry = MemoryEntry(
        entry_id=stable_identifier(
            "memory",
            {
                "certificate_id": bundle.certificate.certificate_id,
                "knowledge_id": knowledge_id,
            },
        ),
        tier=MemoryTier.EPISODIC,
        category="mil_terminal_outcome",
        content={
            "program_id": bundle.program.program_id,
            "goal_id": bundle.program.goal_id,
            "certificate_id": bundle.certificate.certificate_id,
            "disposition": bundle.certificate.disposition.value,
            "verification_status": bundle.verification_result.status.value,
            "reconciliation_status": bundle.reconciliation.status.value,
            "evidence_refs": bundle.certificate.evidence_refs,
        },
        source_ids=(
            bundle.certificate.certificate_id,
            bundle.execution_result.execution_id,
            bundle.verification_result.verification_id,
            bundle.reconciliation.reconciliation_id,
        ),
    )
    admitted = episodic.admit(entry)
    decision = LearningAdmissionDecision(
        _admission_id(knowledge_id, issued_at),
        knowledge_id,
        LearningAdmissionStatus.ADMIT,
        (DecisionReason("committed terminal MIL closure admitted", "mil_learning_admit"),),
        issued_at,
        metadata={"memory_entry_id": admitted.entry_id},
        extensions={"certificate_id": bundle.certificate.certificate_id},
    )
    return MILLearningAdmissionResult(decision, admitted)


def _validate_bundle(bundle: MILTerminalCertificateBundle) -> None:
    if bundle.certificate.command_id != bundle.program.program_id:
        raise RuntimeCoreInvariantError("MIL certificate command mismatch")
    if bundle.certificate.execution_id != bundle.execution_result.execution_id:
        raise RuntimeCoreInvariantError("MIL certificate execution mismatch")
    if bundle.certificate.verification_result_id != bundle.verification_result.verification_id:
        raise RuntimeCoreInvariantError("MIL certificate verification mismatch")
    if bundle.certificate.effect_reconciliation_id != bundle.reconciliation.reconciliation_id:
        raise RuntimeCoreInvariantError("MIL certificate reconciliation mismatch")
    if not bundle.certificate.evidence_refs:
        raise RuntimeCoreInvariantError("MIL learning admission requires certificate evidence")


def _admission_id(knowledge_id: str, issued_at: str) -> str:
    return stable_identifier(
        "mil-learning-admission",
        {"knowledge_id": knowledge_id, "issued_at": issued_at},
    )
