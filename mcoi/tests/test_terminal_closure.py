"""Purpose: tests for terminal command closure certification.
Governance scope: committed, compensated, accepted-risk, and review-required
terminal certificate paths.
Invariants:
  - Committed closure requires pass plus reconciliation MATCH.
  - Compensation closure requires successful compensation.
  - Accepted-risk closure requires active accepted risk.
  - Review closure requires unresolved reconciliation and case.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.accepted_risk import AcceptedRiskDisposition, AcceptedRiskRecord, AcceptedRiskScope
from mcoi_runtime.contracts.compensation import CompensationOutcome, CompensationStatus
from mcoi_runtime.contracts.effect_assurance import EffectReconciliation, ReconciliationStatus
from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.contracts.verification import VerificationCheck, VerificationResult, VerificationStatus
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import MemoryEntry, MemoryTier
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier


NOW = "2026-04-24T16:00:00+00:00"
LIFE_MEANING_REF = "life-meaning:compensation:terminal-1"


def _clock():
    counter = [0]

    def now() -> str:
        value = counter[0]
        counter[0] += 1
        return f"2026-04-24T16:00:{value:02d}+00:00"

    return now


def _execution(*, goal_id: str = "cmd-terminal-1") -> ExecutionResult:
    return ExecutionResult(
        execution_id="exec-terminal-1",
        goal_id=goal_id,
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=(EffectRecord(name="ledger_entry_created", details={"evidence_ref": "ledger:entry-1"}),),
        assumed_effects=(),
        started_at=NOW,
        finished_at="2026-04-24T16:00:01+00:00",
    )


def _verification(
    status: VerificationStatus = VerificationStatus.PASS,
    *,
    metadata: dict[str, str] | None = None,
) -> VerificationResult:
    return VerificationResult(
        verification_id=f"ver-terminal-{status.value}",
        execution_id="exec-terminal-1",
        status=status,
        checks=(VerificationCheck(name="terminal-check", status=status),),
        evidence=(EvidenceRecord(description="terminal evidence", uri="evidence:terminal-1"),),
        closed_at="2026-04-24T16:00:02+00:00",
        metadata=metadata or {},
    )


def _reconciliation(
    status: ReconciliationStatus = ReconciliationStatus.MATCH,
    *,
    command_id: str = "cmd-terminal-1",
    verification_result_id: str = "ver-terminal-pass",
) -> EffectReconciliation:
    return EffectReconciliation(
        reconciliation_id=f"recon-terminal-{status.value}",
        command_id=command_id,
        effect_plan_id="plan-terminal-1",
        status=status,
        matched_effects=("ledger_entry_created",) if status is ReconciliationStatus.MATCH else (),
        missing_effects=() if status is ReconciliationStatus.MATCH else ("ledger_entry_created",),
        unexpected_effects=(),
        verification_result_id=verification_result_id,
        case_id=None if status is ReconciliationStatus.MATCH else "case-terminal-1",
        decided_at="2026-04-24T16:00:03+00:00",
    )


def _accepted_risk(disposition: AcceptedRiskDisposition = AcceptedRiskDisposition.ACTIVE) -> AcceptedRiskRecord:
    return AcceptedRiskRecord(
        risk_id="risk-terminal-1",
        command_id="cmd-terminal-1",
        execution_id="exec-terminal-1",
        effect_plan_id="plan-terminal-1",
        reconciliation_id="recon-terminal-mismatch",
        case_id="case-terminal-1",
        scope=AcceptedRiskScope.EFFECT_RECONCILIATION,
        disposition=disposition,
        reason="bounded unresolved observer gap",
        accepted_by="approver-1",
        owner_id="owner-1",
        expires_at="2026-04-24T17:00:00+00:00",
        review_obligation_id="obl-terminal-1",
        evidence_refs=("provider:receipt-1",),
        accepted_at="2026-04-24T16:00:04+00:00",
    )


def _compensation_outcome(status: CompensationStatus = CompensationStatus.SUCCEEDED) -> CompensationOutcome:
    return CompensationOutcome(
        outcome_id="comp-outcome-terminal-1",
        compensation_plan_id="comp-plan-terminal-1",
        attempt_id="comp-attempt-terminal-1",
        command_id="cmd-terminal-1",
        status=status,
        verification_result_id="ver-comp-terminal-1",
        reconciliation_id="recon-comp-terminal-1",
        life_meaning_judgment_ref=LIFE_MEANING_REF,
        evidence_refs=("refund:receipt-1", LIFE_MEANING_REF),
        decided_at="2026-04-24T16:00:05+00:00",
        case_id=None if status is CompensationStatus.SUCCEEDED else "case-terminal-1",
    )


def _memory_entry() -> MemoryEntry:
    return MemoryEntry(
        entry_id="episodic-terminal-1",
        tier=MemoryTier.EPISODIC,
        category="execution_success",
        content={"trust_class": "trusted"},
        source_ids=("exec-terminal-1", "ver-terminal-pass"),
    )


def test_certifies_committed_closure_with_response_memory_and_evidence():
    certifier = TerminalClosureCertifier(clock=_clock())
    certificate = certifier.certify_committed(
        execution_result=_execution(),
        verification_result=_verification(VerificationStatus.PASS),
        reconciliation=_reconciliation(ReconciliationStatus.MATCH),
        response_closure_ref="response-closure-1",
        memory_entry=_memory_entry(),
        graph_refs=("command:cmd-terminal-1",),
    )
    assert certificate.disposition is TerminalClosureDisposition.COMMITTED
    assert certificate.response_closure_ref == "response-closure-1"
    assert certificate.memory_entry_id == "episodic-terminal-1"
    assert certificate.evidence_refs == ("evidence:terminal-1",)


def test_rejects_committed_closure_without_reconciliation_match():
    certifier = TerminalClosureCertifier(clock=_clock())
    with pytest.raises(RuntimeCoreInvariantError, match="MATCH"):
        certifier.certify_committed(
            execution_result=_execution(),
            verification_result=_verification(VerificationStatus.PASS),
            reconciliation=_reconciliation(ReconciliationStatus.MISMATCH),
        )
    assert certifier.certificate_count == 0


def test_certifies_compensated_closure_with_successful_compensation():
    certifier = TerminalClosureCertifier(clock=_clock())
    certificate = certifier.certify_compensated(
        execution_result=_execution(),
        verification_result=_verification(VerificationStatus.FAIL),
        reconciliation=_reconciliation(
            ReconciliationStatus.MISMATCH,
            verification_result_id="ver-terminal-fail",
        ),
        compensation_outcome=_compensation_outcome(CompensationStatus.SUCCEEDED),
    )
    assert certificate.disposition is TerminalClosureDisposition.COMPENSATED
    assert certificate.compensation_outcome_id == "comp-outcome-terminal-1"
    assert certificate.evidence_refs == ("refund:receipt-1", LIFE_MEANING_REF)
    assert LIFE_MEANING_REF in certificate.evidence_refs
    assert certificate.case_id is None


def test_rejects_compensated_closure_without_successful_compensation():
    certifier = TerminalClosureCertifier(clock=_clock())
    with pytest.raises(RuntimeCoreInvariantError, match="successful compensation"):
        certifier.certify_compensated(
            execution_result=_execution(),
            verification_result=_verification(VerificationStatus.FAIL),
            reconciliation=_reconciliation(
                ReconciliationStatus.MISMATCH,
                verification_result_id="ver-terminal-fail",
            ),
            compensation_outcome=_compensation_outcome(CompensationStatus.REQUIRES_REVIEW),
        )


def test_certifies_accepted_risk_closure_with_case_and_risk():
    certifier = TerminalClosureCertifier(clock=_clock())
    certificate = certifier.certify_accepted_risk(
        execution_result=_execution(),
        verification_result=_verification(VerificationStatus.INCONCLUSIVE),
        reconciliation=_reconciliation(
            ReconciliationStatus.UNKNOWN,
            verification_result_id="ver-terminal-inconclusive",
        ),
        accepted_risk=_accepted_risk(),
    )
    assert certificate.disposition is TerminalClosureDisposition.ACCEPTED_RISK
    assert certificate.accepted_risk_id == "risk-terminal-1"
    assert certificate.case_id == "case-terminal-1"
    assert certificate.evidence_refs == ("provider:receipt-1",)


def test_rejects_accepted_risk_closure_with_expired_risk():
    certifier = TerminalClosureCertifier(clock=_clock())
    with pytest.raises(RuntimeCoreInvariantError, match="active accepted risk"):
        certifier.certify_accepted_risk(
            execution_result=_execution(),
            verification_result=_verification(VerificationStatus.INCONCLUSIVE),
            reconciliation=_reconciliation(
                ReconciliationStatus.UNKNOWN,
                verification_result_id="ver-terminal-inconclusive",
            ),
            accepted_risk=_accepted_risk(AcceptedRiskDisposition.EXPIRED),
        )


def test_certifies_review_required_closure_with_case():
    certifier = TerminalClosureCertifier(clock=_clock())
    certificate = certifier.certify_requires_review(
        execution_result=_execution(),
        verification_result=_verification(VerificationStatus.FAIL),
        reconciliation=_reconciliation(
            ReconciliationStatus.MISMATCH,
            verification_result_id="ver-terminal-fail",
        ),
        case_id="case-terminal-1",
    )
    assert certificate.disposition is TerminalClosureDisposition.REQUIRES_REVIEW
    assert certificate.case_id == "case-terminal-1"
    assert certificate.evidence_refs == ("evidence:terminal-1",)


def test_rejects_review_required_closure_for_matched_reconciliation():
    certifier = TerminalClosureCertifier(clock=_clock())
    with pytest.raises(RuntimeCoreInvariantError, match="unresolved reconciliation"):
        certifier.certify_requires_review(
            execution_result=_execution(),
            verification_result=_verification(VerificationStatus.PASS),
            reconciliation=_reconciliation(ReconciliationStatus.MATCH),
            case_id="case-terminal-1",
        )


def test_rejects_terminal_closure_when_reconciliation_names_wrong_command():
    certifier = TerminalClosureCertifier(clock=_clock())
    with pytest.raises(RuntimeCoreInvariantError, match="reconciliation command mismatch"):
        certifier.certify_committed(
            execution_result=_execution(),
            verification_result=_verification(VerificationStatus.PASS),
            reconciliation=_reconciliation(
                ReconciliationStatus.MATCH,
                command_id="cmd-terminal-other",
            ),
        )
    assert certifier.certificate_count == 0


def test_accepts_terminal_closure_when_reconciliation_matches_verification_program_ref():
    certifier = TerminalClosureCertifier(clock=_clock())
    certificate = certifier.certify_committed(
        execution_result=_execution(goal_id="goal-terminal-1"),
        verification_result=_verification(
            VerificationStatus.PASS,
            metadata={"program_id": "program-terminal-1"},
        ),
        reconciliation=_reconciliation(
            ReconciliationStatus.MATCH,
            command_id="program-terminal-1",
        ),
    )

    assert certificate.command_id == "program-terminal-1"
    assert certificate.disposition is TerminalClosureDisposition.COMMITTED
    assert certifier.certificate_count == 1


def test_rejects_terminal_closure_when_reconciliation_names_wrong_verification():
    certifier = TerminalClosureCertifier(clock=_clock())
    with pytest.raises(RuntimeCoreInvariantError, match="reconciliation verification mismatch"):
        certifier.certify_committed(
            execution_result=_execution(),
            verification_result=_verification(VerificationStatus.PASS),
            reconciliation=_reconciliation(
                ReconciliationStatus.MATCH,
                verification_result_id="ver-terminal-other",
            ),
        )
    assert certifier.certificate_count == 0


def test_terminal_certificate_identity_binds_evidence_refs():
    left = TerminalClosureCertifier(clock=_clock()).certify_committed(
        execution_result=_execution(),
        verification_result=_verification(VerificationStatus.PASS),
        reconciliation=_reconciliation(ReconciliationStatus.MATCH),
        evidence_refs=("proof://verification/left",),
    )
    right = TerminalClosureCertifier(clock=_clock()).certify_committed(
        execution_result=_execution(),
        verification_result=_verification(VerificationStatus.PASS),
        reconciliation=_reconciliation(ReconciliationStatus.MATCH),
        evidence_refs=("proof://verification/right",),
    )

    assert left.certificate_id.startswith("terminal-closure-")
    assert right.certificate_id.startswith("terminal-closure-")
    assert left.certificate_id != right.certificate_id
