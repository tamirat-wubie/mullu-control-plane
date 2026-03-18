"""Purpose: verify completion closure requirements for MCOI execution records.
Governance scope: Milestone 1 contract invariant tests.
Dependencies: pytest and the MCOI verification contract layer.
Invariants: execution closure requires verification or explicit accepted risk.
"""

import pytest

from mcoi_runtime.contracts import (
    AcceptedRiskState,
    EvidenceRecord,
    ExecutionClosure,
    ExecutionOutcome,
    ExecutionResult,
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)


def build_execution_result() -> ExecutionResult:
    return ExecutionResult(
        execution_id="exec-1",
        goal_id="goal-1",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=(),
        assumed_effects=(),
        started_at="2026-03-18T12:00:00+00:00",
        finished_at="2026-03-18T12:01:00+00:00",
    )


def build_verification_result() -> VerificationResult:
    return VerificationResult(
        verification_id="verification-1",
        execution_id="exec-1",
        status=VerificationStatus.PASS,
        checks=(VerificationCheck(name="effects-observed", status=VerificationStatus.PASS),),
        evidence=(EvidenceRecord(description="observer capture"),),
        closed_at="2026-03-18T12:02:00+00:00",
    )


def test_execution_closure_accepts_verification_result() -> None:
    closure = ExecutionClosure(
        execution_result=build_execution_result(),
        verification_result=build_verification_result(),
    )

    assert closure.verification_result is not None
    assert closure.accepted_risk is None
    assert closure.execution_result.execution_id == "exec-1"
    assert closure.verification_result.execution_id == "exec-1"


def test_execution_closure_accepts_explicit_accepted_risk() -> None:
    closure = ExecutionClosure(
        execution_result=build_execution_result(),
        accepted_risk=AcceptedRiskState(
            risk_id="risk-1",
            execution_id="exec-1",
            reason="verification window unavailable",
            accepted_at="2026-03-18T12:02:00+00:00",
        ),
    )

    assert closure.accepted_risk is not None
    assert closure.verification_result is None
    assert closure.accepted_risk.execution_id == "exec-1"
    assert closure.execution_result.execution_id == "exec-1"


def test_execution_closure_requires_verification_or_accepted_risk() -> None:
    with pytest.raises(ValueError) as exc_info:
        ExecutionClosure(execution_result=build_execution_result())

    assert "exactly one" in str(exc_info.value)
    assert "verification_result" in str(exc_info.value)
    assert "accepted_risk" in str(exc_info.value)


def test_execution_closure_rejects_multiple_closure_paths() -> None:
    with pytest.raises(ValueError) as exc_info:
        ExecutionClosure(
            execution_result=build_execution_result(),
            verification_result=build_verification_result(),
            accepted_risk=AcceptedRiskState(
                risk_id="risk-1",
                execution_id="exec-1",
                reason="verification window unavailable",
                accepted_at="2026-03-18T12:02:00+00:00",
            ),
        )

    assert "exactly one" in str(exc_info.value)
    assert "verification_result" in str(exc_info.value)
    assert "accepted_risk" in str(exc_info.value)
