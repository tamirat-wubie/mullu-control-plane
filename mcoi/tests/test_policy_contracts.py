"""Purpose: verify canonical policy status typing for MCOI contracts.
Governance scope: Milestone 1 contract invariant tests.
Dependencies: pytest and the MCOI policy contract layer.
Invariants: policy decisions accept only canonical gate status values.
"""

import pytest

from mcoi_runtime.contracts import DecisionReason, PolicyDecision, PolicyDecisionStatus


def test_policy_decision_accepts_only_canonical_status_values() -> None:
    decision = PolicyDecision(
        decision_id="decision-1",
        subject_id="subject-1",
        goal_id="goal-1",
        status=PolicyDecisionStatus.ALLOW,
        reasons=(DecisionReason(message="admitted knowledge only"),),
        issued_at="2026-03-18T12:00:00+00:00",
    )

    assert decision.status is PolicyDecisionStatus.ALLOW
    assert decision.subject_id == "subject-1"
    assert decision.to_dict()["status"] == "allow"


def test_policy_decision_rejects_invalid_status_values() -> None:
    with pytest.raises(ValueError) as exc_info:
        PolicyDecision(
            decision_id="decision-1",
            subject_id="subject-1",
            goal_id="goal-1",
            status="permit",  # type: ignore[arg-type]
            reasons=(DecisionReason(message="invalid status"),),
            issued_at="2026-03-18T12:00:00+00:00",
        )

    assert "PolicyDecisionStatus" in str(exc_info.value)
    assert "status" in str(exc_info.value)
    assert "permit" not in {status.value for status in PolicyDecisionStatus}
