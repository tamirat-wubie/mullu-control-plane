"""Purpose: terminal closure certification runtime.
Governance scope: final command disposition certification across committed,
compensated, accepted-risk, and review-required paths.
Dependencies: terminal closure contracts, effect assurance, verification,
accepted-risk, compensation, and memory contracts.
Invariants:
  - Commit certification requires reconciliation MATCH and passing verification.
  - Compensation certification requires successful compensation outcome.
  - Accepted-risk certification requires active accepted risk.
  - Review certification requires unresolved reconciliation and case.
"""

from __future__ import annotations

from collections.abc import Callable

from mcoi_runtime.contracts.accepted_risk import AcceptedRiskDisposition, AcceptedRiskRecord
from mcoi_runtime.contracts.compensation import CompensationOutcome, CompensationStatus
from mcoi_runtime.contracts.effect_assurance import EffectReconciliation, ReconciliationStatus
from mcoi_runtime.contracts.execution import ExecutionResult
from mcoi_runtime.contracts.terminal_closure import (
    TerminalClosureCertificate,
    TerminalClosureDisposition,
)
from mcoi_runtime.contracts.verification import VerificationResult, VerificationStatus
from mcoi_runtime.core.memory import MemoryEntry

from .invariants import RuntimeCoreInvariantError, stable_identifier


class TerminalClosureCertifier:
    """Create final command closure certificates."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._certificates: dict[str, TerminalClosureCertificate] = {}

    @property
    def certificate_count(self) -> int:
        """Return total terminal closure certificates."""
        return len(self._certificates)

    def get_certificate(self, certificate_id: str) -> TerminalClosureCertificate | None:
        """Return one terminal closure certificate."""
        return self._certificates.get(certificate_id)

    def certify_committed(
        self,
        *,
        execution_result: ExecutionResult,
        verification_result: VerificationResult,
        reconciliation: EffectReconciliation,
        evidence_refs: tuple[str, ...] | None = None,
        response_closure_ref: str | None = None,
        memory_entry: MemoryEntry | None = None,
        graph_refs: tuple[str, ...] = (),
    ) -> TerminalClosureCertificate:
        """Certify ordinary committed closure."""
        _require_execution_verification_match(execution_result, verification_result)
        if verification_result.status is not VerificationStatus.PASS:
            raise RuntimeCoreInvariantError("committed closure requires passing verification")
        if reconciliation.status is not ReconciliationStatus.MATCH:
            raise RuntimeCoreInvariantError("committed closure requires reconciliation MATCH")
        return self._store(
            self._build(
                command_id=reconciliation.command_id,
                execution_id=execution_result.execution_id,
                disposition=TerminalClosureDisposition.COMMITTED,
                verification_result_id=verification_result.verification_id,
                effect_reconciliation_id=reconciliation.reconciliation_id,
                evidence_refs=evidence_refs or _verification_evidence_refs(verification_result),
                response_closure_ref=response_closure_ref,
                memory_entry_id=memory_entry.entry_id if memory_entry is not None else None,
                graph_refs=graph_refs,
                metadata={"verification_status": verification_result.status.value},
            )
        )

    def certify_compensated(
        self,
        *,
        execution_result: ExecutionResult,
        verification_result: VerificationResult,
        reconciliation: EffectReconciliation,
        compensation_outcome: CompensationOutcome,
        memory_entry: MemoryEntry | None = None,
        graph_refs: tuple[str, ...] = (),
    ) -> TerminalClosureCertificate:
        """Certify compensated terminal closure."""
        _require_execution_verification_match(execution_result, verification_result)
        if reconciliation.status is ReconciliationStatus.MATCH:
            raise RuntimeCoreInvariantError("compensated closure requires unresolved original reconciliation")
        if compensation_outcome.status is not CompensationStatus.SUCCEEDED:
            raise RuntimeCoreInvariantError("compensated closure requires successful compensation")
        return self._store(
            self._build(
                command_id=reconciliation.command_id,
                execution_id=execution_result.execution_id,
                disposition=TerminalClosureDisposition.COMPENSATED,
                verification_result_id=verification_result.verification_id,
                effect_reconciliation_id=reconciliation.reconciliation_id,
                evidence_refs=compensation_outcome.evidence_refs,
                compensation_outcome_id=compensation_outcome.outcome_id,
                memory_entry_id=memory_entry.entry_id if memory_entry is not None else None,
                graph_refs=graph_refs,
                metadata={"compensation_status": compensation_outcome.status.value},
            )
        )

    def certify_accepted_risk(
        self,
        *,
        execution_result: ExecutionResult,
        verification_result: VerificationResult,
        reconciliation: EffectReconciliation,
        accepted_risk: AcceptedRiskRecord,
        memory_entry: MemoryEntry | None = None,
        graph_refs: tuple[str, ...] = (),
    ) -> TerminalClosureCertificate:
        """Certify accepted-risk terminal closure."""
        _require_execution_verification_match(execution_result, verification_result)
        if reconciliation.status is ReconciliationStatus.MATCH:
            raise RuntimeCoreInvariantError("accepted-risk closure requires unresolved reconciliation")
        if accepted_risk.disposition is not AcceptedRiskDisposition.ACTIVE:
            raise RuntimeCoreInvariantError("accepted-risk closure requires active accepted risk")
        if accepted_risk.execution_id != execution_result.execution_id:
            raise RuntimeCoreInvariantError("accepted risk execution mismatch")
        return self._store(
            self._build(
                command_id=reconciliation.command_id,
                execution_id=execution_result.execution_id,
                disposition=TerminalClosureDisposition.ACCEPTED_RISK,
                verification_result_id=verification_result.verification_id,
                effect_reconciliation_id=reconciliation.reconciliation_id,
                evidence_refs=accepted_risk.evidence_refs,
                accepted_risk_id=accepted_risk.risk_id,
                case_id=accepted_risk.case_id,
                memory_entry_id=memory_entry.entry_id if memory_entry is not None else None,
                graph_refs=graph_refs,
                metadata={"accepted_risk_expires_at": accepted_risk.expires_at},
            )
        )

    def certify_requires_review(
        self,
        *,
        execution_result: ExecutionResult,
        verification_result: VerificationResult,
        reconciliation: EffectReconciliation,
        case_id: str,
        evidence_refs: tuple[str, ...] | None = None,
        graph_refs: tuple[str, ...] = (),
    ) -> TerminalClosureCertificate:
        """Certify review-required terminal state."""
        _require_execution_verification_match(execution_result, verification_result)
        if reconciliation.status is ReconciliationStatus.MATCH:
            raise RuntimeCoreInvariantError("review closure requires unresolved reconciliation")
        return self._store(
            self._build(
                command_id=reconciliation.command_id,
                execution_id=execution_result.execution_id,
                disposition=TerminalClosureDisposition.REQUIRES_REVIEW,
                verification_result_id=verification_result.verification_id,
                effect_reconciliation_id=reconciliation.reconciliation_id,
                evidence_refs=evidence_refs or _verification_evidence_refs(verification_result),
                case_id=case_id,
                graph_refs=graph_refs,
                metadata={"reconciliation_status": reconciliation.status.value},
            )
        )

    def _build(
        self,
        *,
        command_id: str,
        execution_id: str,
        disposition: TerminalClosureDisposition,
        verification_result_id: str,
        effect_reconciliation_id: str,
        evidence_refs: tuple[str, ...],
        response_closure_ref: str | None = None,
        memory_entry_id: str | None = None,
        compensation_outcome_id: str | None = None,
        accepted_risk_id: str | None = None,
        case_id: str | None = None,
        graph_refs: tuple[str, ...] = (),
        metadata: dict[str, object] | None = None,
    ) -> TerminalClosureCertificate:
        closed_at = self._clock()
        return TerminalClosureCertificate(
            certificate_id=stable_identifier(
                "terminal-closure",
                {
                    "command_id": command_id,
                    "execution_id": execution_id,
                    "disposition": disposition.value,
                    "closed_at": closed_at,
                },
            ),
            command_id=command_id,
            execution_id=execution_id,
            disposition=disposition,
            verification_result_id=verification_result_id,
            effect_reconciliation_id=effect_reconciliation_id,
            evidence_refs=evidence_refs,
            closed_at=closed_at,
            response_closure_ref=response_closure_ref,
            memory_entry_id=memory_entry_id,
            compensation_outcome_id=compensation_outcome_id,
            accepted_risk_id=accepted_risk_id,
            case_id=case_id,
            graph_refs=graph_refs,
            metadata=metadata or {},
        )

    def _store(self, certificate: TerminalClosureCertificate) -> TerminalClosureCertificate:
        if certificate.certificate_id in self._certificates:
            raise RuntimeCoreInvariantError("terminal closure certificate already exists")
        self._certificates[certificate.certificate_id] = certificate
        return certificate


def _require_execution_verification_match(
    execution_result: ExecutionResult,
    verification_result: VerificationResult,
) -> None:
    if verification_result.execution_id != execution_result.execution_id:
        raise RuntimeCoreInvariantError("verification execution mismatch")


def _verification_evidence_refs(verification_result: VerificationResult) -> tuple[str, ...]:
    evidence_refs = tuple(evidence.uri for evidence in verification_result.evidence)
    if not evidence_refs:
        raise RuntimeCoreInvariantError("terminal closure requires evidence")
    return evidence_refs
