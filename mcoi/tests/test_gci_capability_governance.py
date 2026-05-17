"""Purpose: verify GCI capability governance primitives and execution gates.
Governance scope: capability contracts, T/E/C/R/V axes, source trust, reground,
reality verification, and memory lifecycle decisions.
Dependencies: mcoi_runtime contracts, layers, and governed tool registry.
Invariants:
  - No tool executor runs when capability governance blocks admission.
  - Effectful actions require direct user source trust.
  - Reused execution nodes must pass freshness checks.
"""

from __future__ import annotations

from mcoi_runtime.contracts.capability_contract import (
    CapabilityContract,
    EffectClass,
    IntentSource,
    evaluate_capability_contract,
    op_govdepth,
)
from mcoi_runtime.core.causal_runtime_ledger import CausalRuntimeLedger
from mcoi_runtime.core.governed_tool_gateway import GovernedToolGateway, ToolGatewayRequest
from mcoi_runtime.core.governed_tool_use import GovernedToolRegistry, ToolDefinition
from mcoi_runtime.core.memory_lifecycle import (
    MemoryLifecycleAction,
    MemoryLifecycleFact,
    MemoryLifecyclePolicy,
    evaluate_memory_lifecycle,
)
from mcoi_runtime.core.reground import RegroundNode, RegroundStatus, op_reground
from mcoi_runtime.layers.intent_resolution import IntentCandidate, IntentSet
from mcoi_runtime.layers.reality_verification import (
    RealityObservation,
    RealityVerificationStatus,
    verify_reality_state,
)


def _effectful_contract(*, gov_tier: int = 2, cap_level: int = 2) -> CapabilityContract:
    return CapabilityContract(
        capability="email.send",
        layer="communication",
        cap_level=cap_level,
        gov_tier=gov_tier,
        axis_T="current_episode",
        axis_E="bounded_by_budget",
        axis_C="operator_reviewable",
        axis_R="medium",
        axis_V=EffectClass.EFFECTFUL,
        precond=("registered", "approved"),
        fail_mode=("phi_gov_block", "receipt_recorded"),
        reversible=False,
        intent_source=IntentSource.USER_DIRECT,
    )


def test_effectful_tool_from_monitored_content_blocks_before_executor() -> None:
    calls: list[str] = []
    registry = GovernedToolRegistry(clock=lambda: "2026-05-17T12:00:00Z")
    registry.register(
        ToolDefinition(
            name="email.send",
            description="Send email",
            capability_contract=_effectful_contract(),
        ),
        executor=lambda name, _args: calls.append(name) or {"sent": True},
    )

    result = registry.invoke(
        "email.send",
        {"to": "user@example.com"},
        intent_source=IntentSource.MONITORED_CONTENT,
    )

    assert result.allowed is False
    assert result.capability_decision is not None
    assert "effectful_action_requires_user_direct_intent_source" in result.error
    assert calls == []


def test_cxg_grid_blocks_when_governance_tier_is_below_capability_level() -> None:
    contract = _effectful_contract(gov_tier=1, cap_level=3)

    decision = evaluate_capability_contract(contract)

    assert decision.allowed is False
    assert decision.status.value == "phi_gov_blocked"
    assert decision.capability == "email.send"
    assert decision.reasons == ("governance_tier_below_capability_level",)


def test_value_producing_tool_with_complete_contract_executes() -> None:
    registry = GovernedToolRegistry(clock=lambda: "2026-05-17T12:00:00Z")
    registry.register(
        ToolDefinition(name="docs.summarize", description="Summarize document"),
        executor=lambda _name, args: {"summary": args["text"][:3]},
    )

    result = registry.invoke("docs.summarize", {"text": "abcdef"})

    assert result.allowed is True
    assert result.capability_decision is not None
    assert result.capability_decision.reasons == ("capability_contract_satisfied",)
    assert result.result == {"summary": "abc"}


def test_gateway_records_phi_gov_denial_for_effectful_non_direct_source() -> None:
    gateway = GovernedToolGateway(
        registry=GovernedToolRegistry(clock=lambda: "2026-05-17T12:00:00Z"),
        ledger=CausalRuntimeLedger(clock=lambda: "2026-05-17T12:00:00Z"),
    )
    gateway.register(
        ToolDefinition(
            name="email.send",
            description="Send email",
            capability_contract=_effectful_contract(),
        ),
        executor=lambda _name, _args: {"sent": True},
    )

    result = gateway.invoke(
        ToolGatewayRequest(
            tenant_id="tenant-1",
            actor_id="actor-1",
            session_id="session-1",
            tool_name="email.send",
            intent_source=IntentSource.MONITORED_CONTENT,
        )
    )

    assert result.allowed is False
    assert result.status == "denied"
    assert result.receipt.status == "denied"
    assert "capability_reason:effectful_action_requires_user_direct_intent_source" in result.ledger_event.constraint_refs


def test_intent_set_does_not_authorize_effectful_action_without_direct_source() -> None:
    intent_set = IntentSet((
        IntentCandidate(
            intent="send_email",
            probability=0.92,
            risk_class="medium",
            source_trust=IntentSource.MONITORED_CONTENT,
        ),
    ))

    selected = intent_set.highest_probability()

    assert selected.intent == "send_email"
    assert intent_set.authorizes_effect(EffectClass.VALUE_PRODUCING) is True
    assert intent_set.authorizes_effect(EffectClass.EFFECTFUL) is False


def test_op_reground_detects_stale_reused_node() -> None:
    node = RegroundNode(
        node_id="deployment-state",
        observed_at="2026-05-17T12:00:00+00:00",
        max_age_seconds=60,
        domain="deployment",
    )

    decision = op_reground(node, now="2026-05-17T12:02:01+00:00")

    assert decision.status is RegroundStatus.STALE
    assert decision.age_seconds == 121
    assert decision.reasons == ("node_exceeds_freshness_window",)


def test_reality_verification_detects_digital_reality_divergence() -> None:
    digital = RealityObservation(source="github", claim="deployment", state="deployed", confidence=0.9)
    reality = RealityObservation(source="probe", claim="deployment", state="down", confidence=0.95)

    result = verify_reality_state(
        claim="deployment",
        digital_observation=digital,
        reality_observation=reality,
    )

    assert result.status is RealityVerificationStatus.DIVERGED
    assert result.digital_state == "deployed"
    assert result.reality_state == "down"
    assert result.reasons == ("digital_state_not_equal_reality_state",)


def test_memory_lifecycle_erases_on_consent_withdrawal_and_govdepth_does_not_downgrade_hard_risk() -> None:
    policy = MemoryLifecyclePolicy(
        policy_id="default-memory",
        decay_after_days=30,
        summarize_after_days=60,
        compact_after_days=90,
        erase_after_days=365,
    )
    fact = MemoryLifecycleFact(memory_id="memory-1", age_days=12, consent_active=False)

    lifecycle = evaluate_memory_lifecycle(fact, policy)
    depth = op_govdepth(current_gov_tier=4, requested_gov_tier=1, hard_risk=True)

    assert lifecycle.action is MemoryLifecycleAction.ERASE
    assert lifecycle.reasons == ("consent_withdrawn",)
    assert depth == 4
