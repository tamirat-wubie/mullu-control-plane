"""Purpose: verify deterministic policy mapping for runtime-core.
Governance scope: runtime-core tests only.
Dependencies: the runtime-core policy engine module.
Invariants: policy evaluation returns typed decisions only and remains side-effect free.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from mcoi_runtime.app.policy_packs import PolicyPackRegistry
from mcoi_runtime.governance.policy.engine import PolicyEngine, PolicyInput, PolicyReason


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


def test_policy_engine_applies_strict_approval_pack() -> None:
    engine: PolicyEngine[PolicyDecision] = PolicyEngine(pack_resolver=PolicyPackRegistry())

    decision = engine.evaluate(
        PolicyInput(
            subject_id="subject-1",
            goal_id="goal-1",
            issued_at="2026-03-18T12:00:00+00:00",
            policy_pack_id="strict-approval",
            policy_pack_version="v0.1",
        ),
        build_decision,
    )

    assert decision.status == "escalate"
    assert decision.reasons[0].code == "escalate-all"
    assert decision.decision_id != ""


def test_policy_engine_applies_readonly_pack_for_write_and_read_paths() -> None:
    engine: PolicyEngine[PolicyDecision] = PolicyEngine(pack_resolver=PolicyPackRegistry())

    denied = engine.evaluate(
        PolicyInput(
            subject_id="subject-1",
            goal_id="goal-write",
            issued_at="2026-03-18T12:00:00+00:00",
            policy_pack_id="readonly-only",
            has_write_effects=True,
        ),
        build_decision,
    )
    allowed = engine.evaluate(
        PolicyInput(
            subject_id="subject-1",
            goal_id="goal-read",
            issued_at="2026-03-18T12:00:00+00:00",
            policy_pack_id="readonly-only",
            has_write_effects=False,
        ),
        build_decision,
    )

    assert denied.status == "deny"
    assert denied.reasons[0].code == "deny-writes"
    assert allowed.status == "allow"
    assert allowed.reasons[0].code == "allow-reads"


def test_policy_engine_fails_closed_on_unknown_policy_pack() -> None:
    engine: PolicyEngine[PolicyDecision] = PolicyEngine(pack_resolver=PolicyPackRegistry())

    decision = engine.evaluate(
        PolicyInput(
            subject_id="subject-1",
            goal_id="goal-1",
            issued_at="2026-03-18T12:00:00+00:00",
            policy_pack_id="missing-pack",
        ),
        build_decision,
    )

    assert decision.status == "deny"
    assert decision.reasons[0].code == "unknown_policy_pack"
    assert decision.reasons[0].message == "policy pack unavailable"
    assert "missing-pack" not in decision.reasons[0].message


def test_policy_engine_bounds_no_matching_rule_message() -> None:
    resolver = SimpleNamespace(
        get=lambda pack_id: SimpleNamespace(
            pack_id=pack_id,
            rules=(
                SimpleNamespace(
                    rule_id="never-match",
                    description="unused rule",
                    condition="unknown_condition",
                    action="deny",
                ),
            ),
        )
    )
    engine: PolicyEngine[PolicyDecision] = PolicyEngine(pack_resolver=resolver)

    decision = engine.evaluate(
        PolicyInput(
            subject_id="subject-1",
            goal_id="goal-1",
            issued_at="2026-03-18T12:00:00+00:00",
            policy_pack_id="custom-pack",
        ),
        build_decision,
    )

    assert decision.status == "deny"
    assert decision.reasons[0].code == "no_policy_rule_matched"
    assert decision.reasons[0].message == "no policy rule matched"
    assert "custom-pack" not in decision.reasons[0].message
