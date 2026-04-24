"""Purpose: gate terminal closure memory before learning admission.
Governance scope: episodic-to-semantic/procedural admission decisions for
effect-bearing command closures.
Dependencies: terminal closure, learning, policy reason, and memory contracts.
Invariants:
  - No terminal closure memory becomes reusable knowledge without admission.
  - Accepted-risk closure is deferred, not admitted.
  - Review-required closure is rejected.
  - Admission requires a terminal certificate bound to the episodic memory entry.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Mapping

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
from mcoi_runtime.contracts.policy import DecisionReason
from mcoi_runtime.contracts.terminal_closure import TerminalClosureCertificate, TerminalClosureDisposition

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier
from .memory import MemoryEntry, MemoryTier


class ClosureLearningAdmissionGate:
    """Issue learning admission decisions for terminal closure records."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._decisions: dict[str, LearningAdmissionDecision] = {}

    @property
    def decision_count(self) -> int:
        """Return stored admission decision count."""
        return len(self._decisions)

    def get_decision(self, admission_id: str) -> LearningAdmissionDecision | None:
        """Return a recorded admission decision."""
        ensure_non_empty_text("admission_id", admission_id)
        return self._decisions.get(admission_id)

    def decide(
        self,
        *,
        certificate: TerminalClosureCertificate,
        memory_entry: MemoryEntry,
        learning_scope: str,
        proposed_use: str,
    ) -> LearningAdmissionDecision:
        """Decide whether terminal closure memory may become reusable knowledge."""
        learning_scope = ensure_non_empty_text("learning_scope", learning_scope)
        proposed_use = ensure_non_empty_text("proposed_use", proposed_use)
        _require_certificate_memory_binding(certificate, memory_entry)

        status, reason = _classify(certificate, memory_entry)
        issued_at = self._clock()
        knowledge_id = stable_identifier(
            "closure-knowledge",
            {
                "certificate_id": certificate.certificate_id,
                "memory_entry_id": memory_entry.entry_id,
                "scope": learning_scope,
                "use": proposed_use,
            },
        )
        decision = LearningAdmissionDecision(
            admission_id=stable_identifier(
                "closure-learning-admission",
                {
                    "knowledge_id": knowledge_id,
                    "status": status.value,
                    "issued_at": issued_at,
                },
            ),
            knowledge_id=knowledge_id,
            status=status,
            reasons=(reason,),
            issued_at=issued_at,
            metadata={
                "terminal_certificate_id": certificate.certificate_id,
                "terminal_disposition": certificate.disposition.value,
                "memory_entry_id": memory_entry.entry_id,
                "memory_category": memory_entry.category,
                "trust_class": _trust_class(memory_entry),
                "learning_scope": learning_scope,
                "proposed_use": proposed_use,
                "evidence_refs": certificate.evidence_refs,
            },
        )
        if decision.admission_id in self._decisions:
            raise RuntimeCoreInvariantError("learning admission decision already exists")
        self._decisions[decision.admission_id] = decision
        return decision


def _require_certificate_memory_binding(
    certificate: TerminalClosureCertificate,
    memory_entry: MemoryEntry,
) -> None:
    if memory_entry.tier is not MemoryTier.EPISODIC:
        raise RuntimeCoreInvariantError("terminal closure learning requires episodic memory")
    if certificate.memory_entry_id is None:
        raise RuntimeCoreInvariantError("terminal closure certificate must reference memory_entry_id")
    if certificate.memory_entry_id != memory_entry.entry_id:
        raise RuntimeCoreInvariantError("terminal closure memory entry mismatch")
    if not certificate.evidence_refs:
        raise RuntimeCoreInvariantError("terminal closure learning requires evidence")


def _classify(
    certificate: TerminalClosureCertificate,
    memory_entry: MemoryEntry,
) -> tuple[LearningAdmissionStatus, DecisionReason]:
    disposition = certificate.disposition
    if disposition is TerminalClosureDisposition.COMMITTED:
        return _classify_committed(certificate, memory_entry)
    if disposition is TerminalClosureDisposition.COMPENSATED:
        return _classify_compensated(certificate, memory_entry)
    if disposition is TerminalClosureDisposition.ACCEPTED_RISK:
        return (
            LearningAdmissionStatus.DEFER,
            DecisionReason(
                message="accepted-risk closure cannot become reusable knowledge until the risk is resolved",
                code="terminal_closure.accepted_risk_deferred",
                details=_reason_details(certificate, memory_entry),
            ),
        )
    if disposition is TerminalClosureDisposition.REQUIRES_REVIEW:
        return (
            LearningAdmissionStatus.REJECT,
            DecisionReason(
                message="review-required closure cannot become reusable knowledge",
                code="terminal_closure.review_rejected",
                details=_reason_details(certificate, memory_entry),
            ),
        )
    raise RuntimeCoreInvariantError("unsupported terminal closure disposition")


def _classify_committed(
    certificate: TerminalClosureCertificate,
    memory_entry: MemoryEntry,
) -> tuple[LearningAdmissionStatus, DecisionReason]:
    if memory_entry.category == "execution_success" and _trust_class(memory_entry) == "trusted":
        if memory_entry.content.get("execution_id") != certificate.execution_id:
            return _reject(certificate, memory_entry, "terminal_closure.execution_mismatch")
        return (
            LearningAdmissionStatus.ADMIT,
            DecisionReason(
                message="committed closure with trusted episodic memory is admissible for learning",
                code="terminal_closure.committed_admitted",
                details=_reason_details(certificate, memory_entry),
            ),
        )
    return _reject(certificate, memory_entry, "terminal_closure.untrusted_committed_memory")


def _classify_compensated(
    certificate: TerminalClosureCertificate,
    memory_entry: MemoryEntry,
) -> tuple[LearningAdmissionStatus, DecisionReason]:
    if memory_entry.category == "compensation_success" and _trust_class(memory_entry) == "trusted_compensation":
        if memory_entry.content.get("command_id") != certificate.command_id:
            return _reject(certificate, memory_entry, "terminal_closure.command_mismatch")
        if certificate.compensation_outcome_id not in memory_entry.source_ids:
            return _reject(certificate, memory_entry, "terminal_closure.compensation_source_mismatch")
        return (
            LearningAdmissionStatus.ADMIT,
            DecisionReason(
                message="compensated closure with trusted compensation memory is admissible for learning",
                code="terminal_closure.compensated_admitted",
                details=_reason_details(certificate, memory_entry),
            ),
        )
    return _reject(certificate, memory_entry, "terminal_closure.untrusted_compensation_memory")


def _reject(
    certificate: TerminalClosureCertificate,
    memory_entry: MemoryEntry,
    code: str,
) -> tuple[LearningAdmissionStatus, DecisionReason]:
    return (
        LearningAdmissionStatus.REJECT,
        DecisionReason(
            message="terminal closure memory does not satisfy learning admission requirements",
            code=code,
            details=_reason_details(certificate, memory_entry),
        ),
    )


def _reason_details(
    certificate: TerminalClosureCertificate,
    memory_entry: MemoryEntry,
) -> Mapping[str, Any]:
    return {
        "certificate_id": certificate.certificate_id,
        "command_id": certificate.command_id,
        "execution_id": certificate.execution_id,
        "disposition": certificate.disposition.value,
        "memory_entry_id": memory_entry.entry_id,
        "memory_category": memory_entry.category,
        "trust_class": _trust_class(memory_entry),
    }


def _trust_class(memory_entry: MemoryEntry) -> str | None:
    trust_class = memory_entry.content.get("trust_class")
    if trust_class is None:
        return None
    if not isinstance(trust_class, str):
        raise RuntimeCoreInvariantError("memory trust_class must be text when present")
    return trust_class
