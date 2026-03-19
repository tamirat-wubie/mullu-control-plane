"""Purpose: verify canonical execution outcome typing for MCOI contracts.
Governance scope: Milestone 1 contract invariant tests.
Dependencies: pytest and the MCOI execution contract layer.
Invariants: execution results accept only canonical outcome values.
"""

import pytest

from mcoi_runtime.contracts import ExecutionOutcome, ExecutionResult


def test_execution_result_accepts_only_canonical_outcomes() -> None:
    result = ExecutionResult(
        execution_id="exec-1",
        goal_id="goal-1",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=(),
        assumed_effects=(),
        started_at="2026-03-18T12:00:00+00:00",
        finished_at="2026-03-18T12:01:00+00:00",
    )

    assert result.status is ExecutionOutcome.SUCCEEDED
    assert result.execution_id == "exec-1"
    assert result.to_dict()["status"] == "succeeded"


def test_execution_result_rejects_invalid_outcomes() -> None:
    with pytest.raises(ValueError) as exc_info:
        ExecutionResult(
            execution_id="exec-1",
            goal_id="goal-1",
            status="unknown",  # type: ignore[arg-type]
            actual_effects=(),
            assumed_effects=(),
            started_at="2026-03-18T12:00:00+00:00",
            finished_at="2026-03-18T12:01:00+00:00",
        )

    assert "ExecutionOutcome" in str(exc_info.value)
    assert "status" in str(exc_info.value)
    assert "unknown" not in {outcome.value for outcome in ExecutionOutcome}
