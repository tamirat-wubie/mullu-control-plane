"""Purpose: tests for closure-to-episodic-memory promotion.
Governance scope: verified execution, accepted-risk, failure, and compensation
episodic memory admission.
Invariants:
  - Passing verification admits trusted execution memory.
  - Failed verification admits only failure memory.
  - Inconclusive verification requires active accepted risk.
  - Successful compensation admits trusted compensation memory.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.accepted_risk import (
    AcceptedRiskDisposition,
    AcceptedRiskRecord,
    AcceptedRiskScope,
)
from mcoi_runtime.contracts.compensation import CompensationOutcome, CompensationStatus
from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.verification import VerificationCheck, VerificationResult, VerificationStatus
from mcoi_runtime.core.closure_memory import ClosureMemoryPromoter
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import EpisodicMemory


NOW = "2026-04-24T15:00:00+00:00"


def _clock():
    counter = [0]

    def now() -> str:
        value = counter[0]
        counter[0] += 1
        return f"2026-04-24T15:00:{value:02d}+00:00"

    return now


def _execution() -> ExecutionResult:
    return ExecutionResult(
        execution_id="exec-memory-1",
        goal_id="cmd-memory-1",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=(EffectRecord(name="ledger_entry_created", details={"evidence_ref": "ledger:entry-1"}),),
        assumed_effects=(),
        started_at=NOW,
        finished_at="2026-04-24T15:00:01+00:00",
        metadata={"tenant_id": "tenant-1"},
    )


def _verification(status: VerificationStatus = VerificationStatus.PASS) -> VerificationResult:
    return VerificationResult(
        verification_id=f"ver-memory-{status.value}",
        execution_id="exec-memory-1",
        status=status,
        checks=(VerificationCheck(name="effect-check", status=status),),
        evidence=(EvidenceRecord(description="ledger proof", uri="ledger:entry-1"),),
        closed_at="2026-04-24T15:00:02+00:00",
        metadata={"command_id": "cmd-memory-1"},
    )


def _accepted_risk(disposition: AcceptedRiskDisposition = AcceptedRiskDisposition.ACTIVE) -> AcceptedRiskRecord:
    return AcceptedRiskRecord(
        risk_id="risk-memory-1",
        command_id="cmd-memory-1",
        execution_id="exec-memory-1",
        effect_plan_id="plan-memory-1",
        reconciliation_id="recon-memory-1",
        case_id="case-memory-1",
        scope=AcceptedRiskScope.EFFECT_RECONCILIATION,
        disposition=disposition,
        reason="observer inconclusive with provider evidence",
        accepted_by="approver-1",
        owner_id="owner-1",
        expires_at="2026-04-24T16:00:00+00:00",
        review_obligation_id="obl-memory-1",
        evidence_refs=("provider:receipt-1",),
        accepted_at="2026-04-24T15:00:03+00:00",
    )


def _promoter():
    episodic = EpisodicMemory()
    return ClosureMemoryPromoter(episodic=episodic, clock=_clock()), episodic


def test_admits_passing_verified_execution_as_trusted_episodic_memory():
    promoter, episodic = _promoter()
    entry = promoter.admit_execution_closure(
        execution_result=_execution(),
        verification_result=_verification(VerificationStatus.PASS),
    )
    assert entry.category == "execution_success"
    assert entry.content["trust_class"] == "trusted"
    assert entry.content["verification_status"] == "pass"
    assert episodic.get(entry.entry_id) is entry


def test_admits_failed_verification_as_failure_record_not_trusted_success():
    promoter, episodic = _promoter()
    entry = promoter.admit_execution_closure(
        execution_result=_execution(),
        verification_result=_verification(VerificationStatus.FAIL),
    )
    assert entry.category == "execution_failure"
    assert entry.content["trust_class"] == "failure_record"
    assert entry.content["verification_status"] == "fail"
    assert episodic.size == 1


def test_rejects_inconclusive_verification_without_accepted_risk():
    promoter, episodic = _promoter()
    with pytest.raises(RuntimeCoreInvariantError, match="accepted risk"):
        promoter.admit_execution_closure(
            execution_result=_execution(),
            verification_result=_verification(VerificationStatus.INCONCLUSIVE),
        )
    assert episodic.size == 0


def test_admits_inconclusive_verification_with_active_accepted_risk():
    promoter, episodic = _promoter()
    entry = promoter.admit_execution_closure(
        execution_result=_execution(),
        verification_result=_verification(VerificationStatus.INCONCLUSIVE),
        accepted_risk=_accepted_risk(),
    )
    assert entry.category == "execution_accepted_risk"
    assert entry.content["trust_class"] == "accepted_risk"
    assert entry.content["accepted_risk"]["risk_id"] == "risk-memory-1"
    assert entry.source_ids[-1] == "risk-memory-1"


def test_rejects_inconclusive_verification_with_expired_accepted_risk():
    promoter, _ = _promoter()
    with pytest.raises(RuntimeCoreInvariantError, match="active"):
        promoter.admit_execution_closure(
            execution_result=_execution(),
            verification_result=_verification(VerificationStatus.INCONCLUSIVE),
            accepted_risk=_accepted_risk(AcceptedRiskDisposition.EXPIRED),
        )


def test_admits_successful_compensation_outcome_as_trusted_compensation_memory():
    promoter, episodic = _promoter()
    outcome = CompensationOutcome(
        outcome_id="comp-outcome-memory-1",
        compensation_plan_id="comp-plan-memory-1",
        attempt_id="comp-attempt-memory-1",
        command_id="cmd-memory-1",
        status=CompensationStatus.SUCCEEDED,
        verification_result_id="ver-comp-memory-1",
        reconciliation_id="recon-comp-memory-1",
        evidence_refs=("refund:receipt-1",),
        decided_at="2026-04-24T15:00:04+00:00",
    )
    entry = promoter.admit_compensation_outcome(outcome)
    assert entry.category == "compensation_success"
    assert entry.content["trust_class"] == "trusted_compensation"
    assert entry.source_ids == ("comp-outcome-memory-1", "ver-comp-memory-1", "recon-comp-memory-1")
    assert episodic.size == 1


def test_rejects_unresolved_compensation_outcome_from_trusted_memory():
    promoter, episodic = _promoter()
    outcome = CompensationOutcome(
        outcome_id="comp-outcome-memory-2",
        compensation_plan_id="comp-plan-memory-1",
        attempt_id="comp-attempt-memory-1",
        command_id="cmd-memory-1",
        status=CompensationStatus.REQUIRES_REVIEW,
        verification_result_id="ver-comp-memory-1",
        reconciliation_id="recon-comp-memory-1",
        evidence_refs=("refund:request-1",),
        decided_at="2026-04-24T15:00:04+00:00",
        case_id="case-comp-1",
    )
    with pytest.raises(RuntimeCoreInvariantError, match="successful compensation"):
        promoter.admit_compensation_outcome(outcome)
    assert episodic.size == 0
