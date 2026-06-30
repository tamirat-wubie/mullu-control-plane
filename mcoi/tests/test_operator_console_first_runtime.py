"""Purpose: verify Operator Console First runtime gateway behavior.
Governance scope: episode contracts, approval leases, side-effect gates,
    independent verification, receipt outcomes, and cost/freshness guards.
Dependencies: operator_console_first contracts and runtime core.
Invariants:
  - Read-only actions may run without approval but still emit receipts.
  - External effectful actions require state-bound approval leases.
  - Plan, state, side-effect, recovery, and cost violations fail closed.
"""

from __future__ import annotations

from dataclasses import replace

from mcoi_runtime.contracts.operator_console_first import (
    ConsoleEpisodeStatus,
    ConsoleFinalStatus,
    ConsoleIntentClass,
    ConsolePlannedAction,
    EpisodeLimits,
    GatewayDispatchResult,
    HostileInputBoundary,
    RecoveryClass,
    SideEffectManifest,
    StateSnapshot,
)
from mcoi_runtime.core.operator_console_first import (
    OperatorConsoleFirstRuntime,
    approval_mode_for_action,
    score_action_risk,
)
from mcoi_runtime.contracts.operator_console_first import ApprovalMode


_NOW = "2026-06-30T12:00:00Z"
_FUTURE = "2026-06-30T12:30:00Z"


class FakeGateway:
    def __init__(self, result: GatewayDispatchResult) -> None:
        self.result = result
        self.calls: list[str] = []

    def dispatch(self, _episode, action: ConsolePlannedAction) -> GatewayDispatchResult:
        self.calls.append(action.action_id)
        return self.result


def _runtime() -> OperatorConsoleFirstRuntime:
    return OperatorConsoleFirstRuntime(clock=lambda: _NOW)


def _snapshot() -> StateSnapshot:
    return StateSnapshot(
        source="unit-test",
        captured_at=_NOW,
        expires_at=_FUTURE,
        state_hash="state-abc",
        trust_level=1.0,
    )


def _episode(
    intent_class: ConsoleIntentClass = ConsoleIntentClass.OBSERVE,
    *,
    limits: EpisodeLimits | None = None,
):
    return _runtime().capture_episode(
        operator_id="operator-1",
        raw_request="inspect current state",
        intent_class=intent_class,
        governed_goal={"objective": "prove current state"},
        scope={"target": "local"},
        snapshot=_snapshot(),
        limits=limits,
    )


def _action(
    *,
    action_id: str = "act-read",
    intent_class: ConsoleIntentClass = ConsoleIntentClass.OBSERVE,
    risk_score: int = 10,
    effects: tuple[str, ...] = ("state_read",),
    side_effects: SideEffectManifest | None = None,
    declared: bool = True,
    recovery_class: RecoveryClass = RecoveryClass.R0_NONE,
    recovery_ref: str = "",
    estimated_cost: float = 0.0,
    hostile_input_boundary: HostileInputBoundary | None = None,
) -> ConsolePlannedAction:
    return ConsolePlannedAction(
        action_id=action_id,
        capability_id="capability.local.observe",
        intent_class=intent_class,
        risk_score=risk_score,
        expected_effects=effects,
        side_effects_declared=declared,
        side_effects=side_effects or SideEffectManifest(reads_data=True),
        recovery_class=recovery_class,
        recovery_plan_ref=recovery_ref,
        evidence_required=("receipt",),
        estimated_cost=estimated_cost,
        hostile_input_boundary=hostile_input_boundary or HostileInputBoundary(),
    )


def test_read_only_task_runs_without_approval_and_emits_verified_receipt() -> None:
    runtime = _runtime()
    action = _action()
    episode = runtime.plan_episode(_episode(), (action,))
    gateway = FakeGateway(
        GatewayDispatchResult(
            action_id=action.action_id,
            tool_success=True,
            observed_effects=("state_read",),
            evidence_refs=("evidence://state-read",),
        )
    )

    final_episode, receipt = runtime.execute_episode(episode, gateway=gateway)

    assert episode.approval_lease is None
    assert episode.status is ConsoleEpisodeStatus.PLANNED
    assert gateway.calls == ["act-read"]
    assert final_episode.status is ConsoleEpisodeStatus.CLOSED
    assert receipt.final_status is ConsoleFinalStatus.VERIFIED_SUCCESS
    assert receipt.actions_attempted == ("act-read",)
    assert receipt.actions_blocked == ()


def test_external_irreversible_action_requires_state_bound_approval() -> None:
    runtime = _runtime()
    action = _action(
        action_id="act-send",
        intent_class=ConsoleIntentClass.EXTERNAL_IRREVERSIBLE,
        risk_score=60,
        effects=("message_sent",),
        side_effects=SideEffectManifest(sends_external_data=True, uses_network=True),
        recovery_class=RecoveryClass.R2_COMPENSATING_ACTION,
        recovery_ref="recovery://send-correction",
    )
    episode = runtime.plan_episode(_episode(ConsoleIntentClass.EXTERNAL_IRREVERSIBLE), (action,))
    gateway = FakeGateway(
        GatewayDispatchResult(
            action_id=action.action_id,
            tool_success=True,
            observed_effects=("message_sent",),
            evidence_refs=("evidence://sent-message-id",),
        )
    )

    blocked_episode, blocked_receipt = runtime.execute_episode(episode, gateway=gateway)
    approved = runtime.issue_approval(episode, operator_id="approver-1")
    final_episode, receipt = runtime.execute_episode(approved, gateway=gateway)

    assert episode.status is ConsoleEpisodeStatus.WAITING_APPROVAL
    assert blocked_episode.status is ConsoleEpisodeStatus.BLOCKED
    assert blocked_receipt.final_status is ConsoleFinalStatus.BLOCKED
    assert blocked_receipt.unverified_claims == ("missing_approval_lease",)
    assert approved.approval_lease is not None
    assert final_episode.status is ConsoleEpisodeStatus.CLOSED
    assert receipt.final_status is ConsoleFinalStatus.VERIFIED_SUCCESS


def test_approval_expires_when_plan_or_target_state_changes() -> None:
    runtime = _runtime()
    action = _action(
        action_id="act-publish",
        intent_class=ConsoleIntentClass.EXTERNAL_IRREVERSIBLE,
        risk_score=61,
        effects=("release_published",),
        side_effects=SideEffectManifest(changes_public_state=True, uses_network=True),
        recovery_class=RecoveryClass.R3_CONTAINMENT,
        recovery_ref="recovery://contain-release",
    )
    approved = runtime.issue_approval(
        runtime.plan_episode(_episode(ConsoleIntentClass.EXTERNAL_IRREVERSIBLE), (action,)),
        operator_id="approver-1",
    )
    mutated_action = replace(action, expected_effects=("release_published", "audit_recorded"))
    changed_plan_episode = replace(approved, plan=(mutated_action,))

    plan_decision = runtime.can_dispatch(changed_plan_episode, mutated_action)
    state_decision = runtime.can_dispatch(approved, action, current_state_hash="state-changed")

    assert approved.approval_lease is not None
    assert plan_decision.allowed is False
    assert plan_decision.reason == "approval_plan_mismatch"
    assert state_decision.allowed is False
    assert state_decision.reason == "approval_state_mismatch"


def test_gateway_blocks_undeclared_side_effects_and_missing_recovery() -> None:
    runtime = _runtime()
    undeclared = _action(
        action_id="act-network",
        side_effects=SideEffectManifest(uses_network=True),
        declared=False,
        recovery_class=RecoveryClass.R1_DIRECT_ROLLBACK,
        recovery_ref="recovery://network",
    )
    missing_recovery = _action(
        action_id="act-write",
        side_effects=SideEffectManifest(writes_data=True),
        recovery_class=RecoveryClass.R2_COMPENSATING_ACTION,
    )
    undeclared_episode = runtime.plan_episode(_episode(), (undeclared,))
    missing_recovery_episode = runtime.plan_episode(_episode(), (missing_recovery,))

    undeclared_decision = runtime.can_dispatch(undeclared_episode, undeclared)
    missing_recovery_decision = runtime.can_dispatch(missing_recovery_episode, missing_recovery)

    assert undeclared_decision.allowed is False
    assert undeclared_decision.reason == "undeclared_side_effects"
    assert missing_recovery_decision.allowed is False
    assert missing_recovery_decision.reason == "missing_recovery_plan"


def test_tool_success_without_independent_evidence_is_unverified() -> None:
    runtime = _runtime()
    action = _action(
        action_id="act-draft",
        intent_class=ConsoleIntentClass.INTERNAL_REVERSIBLE,
        risk_score=25,
        effects=("draft_created",),
        side_effects=SideEffectManifest(writes_data=True),
        recovery_class=RecoveryClass.R1_DIRECT_ROLLBACK,
        recovery_ref="recovery://delete-draft",
    )
    episode = runtime.plan_episode(_episode(ConsoleIntentClass.INTERNAL_REVERSIBLE), (action,))
    gateway = FakeGateway(
        GatewayDispatchResult(
            action_id=action.action_id,
            tool_success=True,
            observed_effects=("draft_created",),
            evidence_refs=(),
        )
    )

    final_episode, receipt = runtime.execute_episode(episode, gateway=gateway)

    assert gateway.calls == ["act-draft"]
    assert final_episode.status is ConsoleEpisodeStatus.CLOSED
    assert receipt.final_status is ConsoleFinalStatus.UNVERIFIED_SUCCESS
    assert receipt.verification_records[0].independently_verified is False
    assert receipt.unverified_claims == ("independent_evidence_missing",)


def test_partial_completion_redacts_sensitive_evidence_reference() -> None:
    runtime = _runtime()
    action = _action(
        action_id="act-attach",
        effects=("draft_created", "attachment_added"),
        side_effects=SideEffectManifest(writes_data=True),
        recovery_class=RecoveryClass.R1_DIRECT_ROLLBACK,
        recovery_ref="recovery://delete-draft",
    )
    episode = runtime.plan_episode(_episode(), (action,))
    gateway = FakeGateway(
        GatewayDispatchResult(
            action_id=action.action_id,
            tool_success=True,
            observed_effects=("draft_created",),
            evidence_refs=("secret-token://provider/raw-value",),
        )
    )

    _final_episode, receipt = runtime.execute_episode(episode, gateway=gateway)

    assert receipt.final_status is ConsoleFinalStatus.PARTIAL_SUCCESS
    assert receipt.verification_records[0].missing_effects == ("attachment_added",)
    assert receipt.evidence_refs[0].startswith("redacted-sensitive-ref:")
    assert "secret-token" not in receipt.evidence_refs[0]
    assert receipt.unverified_claims == ("attachment_added",)


def test_hidden_side_effect_quarantines_after_gateway_observation() -> None:
    runtime = _runtime()
    action = _action(action_id="act-summary")
    episode = runtime.plan_episode(_episode(), (action,))
    gateway = FakeGateway(
        GatewayDispatchResult(
            action_id=action.action_id,
            tool_success=True,
            observed_effects=("state_read",),
            evidence_refs=("evidence://summary",),
            actual_side_effects=SideEffectManifest(reads_data=True, uses_network=True),
        )
    )

    final_episode, receipt = runtime.execute_episode(episode, gateway=gateway)

    assert gateway.calls == ["act-summary"]
    assert final_episode.status is ConsoleEpisodeStatus.QUARANTINED
    assert receipt.final_status is ConsoleFinalStatus.QUARANTINED
    assert receipt.unverified_claims == ("uses_network",)


def test_hostile_external_input_cannot_grant_authority_or_approval() -> None:
    runtime = _runtime()
    action = _action(
        action_id="act-hostile-doc",
        side_effects=SideEffectManifest(reads_data=True),
        hostile_input_boundary=HostileInputBoundary(
            external_content_refs=("doc://untrusted/comment-1",),
            attempts_approval_claim=True,
            attempts_policy_override=True,
        ),
    )
    episode = runtime.plan_episode(_episode(), (action,))
    gateway = FakeGateway(
        GatewayDispatchResult(
            action_id=action.action_id,
            tool_success=True,
            observed_effects=("state_read",),
            evidence_refs=("evidence://unused",),
        )
    )

    final_episode, receipt = runtime.execute_episode(episode, gateway=gateway)

    assert gateway.calls == []
    assert final_episode.status is ConsoleEpisodeStatus.POLICY_DENIED
    assert receipt.final_status is ConsoleFinalStatus.BLOCKED
    assert receipt.actions_blocked == ("act-hostile-doc",)
    assert receipt.unverified_claims == ("hostile_input_authority_violation",)


def test_risk_escalation_pauses_workflow_before_verified_completion() -> None:
    runtime = _runtime()
    action = _action(
        action_id="act-risk-escalates",
        intent_class=ConsoleIntentClass.INTERNAL_REVERSIBLE,
        risk_score=20,
        effects=("draft_created",),
        side_effects=SideEffectManifest(writes_data=True),
        recovery_class=RecoveryClass.R1_DIRECT_ROLLBACK,
        recovery_ref="recovery://delete-draft",
    )
    episode = runtime.plan_episode(_episode(ConsoleIntentClass.INTERNAL_REVERSIBLE), (action,))
    gateway = FakeGateway(
        GatewayDispatchResult(
            action_id=action.action_id,
            tool_success=True,
            observed_effects=("draft_created",),
            evidence_refs=("evidence://draft",),
            escalated_risk_score=60,
        )
    )

    final_episode, receipt = runtime.execute_episode(episode, gateway=gateway)

    assert gateway.calls == ["act-risk-escalates"]
    assert final_episode.status is ConsoleEpisodeStatus.PAUSED
    assert receipt.final_status is ConsoleFinalStatus.BLOCKED
    assert receipt.actions_attempted == ("act-risk-escalates",)
    assert receipt.actions_blocked == ("act-risk-escalates",)
    assert receipt.unverified_claims == ("risk_escalated",)


def test_risk_escalation_above_approval_ceiling_pauses_same_lane() -> None:
    runtime = _runtime()
    action = _action(
        action_id="act-approved-risk-escalates",
        intent_class=ConsoleIntentClass.EXTERNAL_IRREVERSIBLE,
        risk_score=46,
        effects=("message_sent",),
        side_effects=SideEffectManifest(sends_external_data=True, uses_network=True),
        recovery_class=RecoveryClass.R2_COMPENSATING_ACTION,
        recovery_ref="recovery://send-correction",
    )
    approved = runtime.issue_approval(
        runtime.plan_episode(_episode(ConsoleIntentClass.EXTERNAL_IRREVERSIBLE), (action,)),
        operator_id="approver-1",
        risk_ceiling=46,
    )
    gateway = FakeGateway(
        GatewayDispatchResult(
            action_id=action.action_id,
            tool_success=True,
            observed_effects=("message_sent",),
            evidence_refs=("evidence://message",),
            escalated_risk_score=50,
        )
    )

    final_episode, receipt = runtime.execute_episode(approved, gateway=gateway)

    assert approved.approval_lease is not None
    assert gateway.calls == ["act-approved-risk-escalates"]
    assert final_episode.status is ConsoleEpisodeStatus.PAUSED
    assert receipt.final_status is ConsoleFinalStatus.BLOCKED
    assert receipt.unverified_claims == ("risk_escalated",)


def test_abort_before_dispatch_emits_aborted_receipt() -> None:
    runtime = _runtime()
    action = _action(action_id="act-abortable")
    episode = runtime.plan_episode(_episode(), (action,))
    gateway = FakeGateway(
        GatewayDispatchResult(
            action_id=action.action_id,
            tool_success=True,
            observed_effects=("state_read",),
            evidence_refs=("evidence://unused",),
        )
    )

    final_episode, receipt = runtime.execute_episode(
        episode,
        gateway=gateway,
        abort_requested=lambda _episode, _action: True,
    )

    assert gateway.calls == []
    assert final_episode.status is ConsoleEpisodeStatus.ABORTED
    assert receipt.final_status is ConsoleFinalStatus.ABORTED
    assert receipt.actions_attempted == ()
    assert receipt.actions_blocked == ("act-abortable",)
    assert receipt.unverified_claims == ("operator_abort_requested",)


def test_cost_limit_stops_runaway_execution_before_gateway() -> None:
    runtime = _runtime()
    action = _action(action_id="act-costly", estimated_cost=10.0)
    episode = runtime.plan_episode(_episode(limits=EpisodeLimits(max_cost=5.0)), (action,))
    gateway = FakeGateway(
        GatewayDispatchResult(
            action_id=action.action_id,
            tool_success=True,
            observed_effects=("state_read",),
            evidence_refs=("evidence://unused",),
        )
    )

    final_episode, receipt = runtime.execute_episode(episode, gateway=gateway)

    assert gateway.calls == []
    assert final_episode.status is ConsoleEpisodeStatus.POLICY_DENIED
    assert receipt.final_status is ConsoleFinalStatus.BLOCKED
    assert receipt.unverified_claims == ("cost_limit_exceeded",)


def test_risk_score_is_bounded_and_maps_to_approval_modes() -> None:
    low_action = _action(risk_score=20)
    high_action = _action(
        risk_score=46,
        intent_class=ConsoleIntentClass.EXTERNAL_IRREVERSIBLE,
        side_effects=SideEffectManifest(uses_network=True),
        recovery_class=RecoveryClass.R2_COMPENSATING_ACTION,
        recovery_ref="recovery://compensate",
    )
    critical_action = _action(
        risk_score=71,
        intent_class=ConsoleIntentClass.CRITICAL,
        side_effects=SideEffectManifest(changes_money=True),
        recovery_class=RecoveryClass.R4_MANUAL_ESCALATION,
        recovery_ref="recovery://manual",
    )

    score = score_action_risk(
        impact=20,
        irreversibility=20,
        uncertainty=20,
        data_sensitivity=20,
        externality=20,
        novelty=20,
        blast_radius=20,
        cost_exposure=20,
        permission_power=20,
        recovery_confidence=0,
        evidence_strength=0,
    )

    assert score == 100
    assert approval_mode_for_action(low_action) is ApprovalMode.AUTO
    assert approval_mode_for_action(high_action) is ApprovalMode.EXPLICIT
    assert approval_mode_for_action(critical_action) is ApprovalMode.STRONG
