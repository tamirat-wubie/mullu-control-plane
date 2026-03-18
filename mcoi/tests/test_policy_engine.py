"""Purpose: verify deterministic policy mapping for runtime-core.
Governance scope: runtime-core tests only.
Dependencies: the runtime-core policy engine module.
Invariants: policy evaluation returns typed decisions only and remains side-effect free.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.core.policy_engine import PolicyEngine, PolicyInput, PolicyReason


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    decision_id: str
    subject_id: str
    goal_id: str
    status: str
    reasons: tuple[PolicyReason, ...]
    issued_at: str


def build_decision(**kwargs: object) -> PolicyDecision:
    return PolicyDecision(**kwargs)


def test_policy_engine_returns_typed_allow_decisions_deterministically() -> None:
    engine: PolicyEngine[PolicyDecision] = PolicyEngine()
    policy_input = PolicyInput(
        subject_id="subject-1",
        goal_id="goal-1",
        issued_at="2026-03-18T12:00:00+00:00",
    )

    first = engine.evaluate(policy_input, build_decision)
    second = engine.evaluate(policy_input, build_decision)

    assert isinstance(first, PolicyDecision)
    assert first.status == "allow"
    assert first.decision_id == second.decision_id
    assert first.reasons[0].code == "policy_conditions_satisfied"


def test_policy_engine_denies_and_escalates_on_explicit_inputs() -> None:
    engine: PolicyEngine[PolicyDecision] = PolicyEngine()

    denied = engine.evaluate(
        PolicyInput(
            subject_id="subject-1",
            goal_id="goal-1",
            issued_at="2026-03-18T12:00:00+00:00",
            blocked_knowledge_ids=("knowledge-9",),
        ),
        build_decision,
    )
    escalated = engine.evaluate(
        PolicyInput(
            subject_id="subject-1",
            goal_id="goal-1",
            issued_at="2026-03-18T12:00:00+00:00",
            missing_capability_ids=("capability-2",),
        ),
        build_decision,
    )

    assert denied.status == "deny"
    assert denied.reasons[0].code == "blocked_knowledge"
    assert escalated.status == "escalate"
    assert escalated.reasons[0].code == "operator_review_required"
