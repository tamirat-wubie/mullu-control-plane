"""Purpose: verify deterministic verification closure for the MCOI runtime.
Governance scope: verification-core tests only.
Dependencies: canonical execution and verification contracts and the verification engine.
Invariants: completion is explicit, mismatches fail closed, and non-success execution outcomes never become complete.
"""

from __future__ import annotations

from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.verification import VerificationCheck, VerificationResult, VerificationStatus
from mcoi_runtime.core.verification_engine import VerificationEngine


def make_execution_result(*, execution_id: str, status: ExecutionOutcome) -> ExecutionResult:
    return ExecutionResult(
        execution_id=execution_id,
        goal_id="goal-1",
        status=status,
        actual_effects=(EffectRecord(name="process_completed", details={"ok": True}),),
        assumed_effects=(),
        started_at="2026-03-18T12:00:00+00:00",
        finished_at="2026-03-18T12:00:01+00:00",
    )


def make_verification_result(
    *,
    execution_id: str,
    status: VerificationStatus,
) -> VerificationResult:
    return VerificationResult(
        verification_id="verification-1",
        execution_id=execution_id,
        status=status,
        checks=(VerificationCheck(name="stdout_present", status=status),),
        evidence=(EvidenceRecord(description="verification.evidence", details={"ok": True}),),
        closed_at="2026-03-18T12:00:02+00:00",
    )


def test_verification_engine_leaves_execution_open_without_verification() -> None:
    engine = VerificationEngine()
    result = engine.evaluate(
        make_execution_result(execution_id="execution-1", status=ExecutionOutcome.SUCCEEDED),
        None,
    )

    assert result.verification_closed is False
    assert result.completed is False
    assert result.error is None


def test_verification_engine_closes_and_completes_on_matching_positive_verification() -> None:
    engine = VerificationEngine()
    result = engine.evaluate(
        make_execution_result(execution_id="execution-2", status=ExecutionOutcome.SUCCEEDED),
        make_verification_result(execution_id="execution-2", status=VerificationStatus.PASS),
    )

    assert result.verification_closed is True
    assert result.completed is True
    assert result.error is None


def test_verification_engine_closes_but_does_not_complete_on_failed_verification() -> None:
    engine = VerificationEngine()
    result = engine.evaluate(
        make_execution_result(execution_id="execution-3", status=ExecutionOutcome.SUCCEEDED),
        make_verification_result(execution_id="execution-3", status=VerificationStatus.FAIL),
    )

    assert result.verification_closed is True
    assert result.completed is False
    assert result.error is None


def test_verification_engine_rejects_mismatched_verification_identity() -> None:
    engine = VerificationEngine()
    result = engine.evaluate(
        make_execution_result(execution_id="execution-4", status=ExecutionOutcome.SUCCEEDED),
        make_verification_result(execution_id="execution-other", status=VerificationStatus.PASS),
    )

    assert result.verification_closed is False
    assert result.completed is False
    assert result.error == "verification_execution_mismatch"


def test_verification_engine_never_completes_non_success_execution_outcomes() -> None:
    engine = VerificationEngine()
    result = engine.evaluate(
        make_execution_result(execution_id="execution-5", status=ExecutionOutcome.FAILED),
        make_verification_result(execution_id="execution-5", status=VerificationStatus.PASS),
    )

    assert result.verification_closed is True
    assert result.completed is False
    assert result.error == "execution_outcome_not_completable"
