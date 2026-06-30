"""Purpose: verify Operator Console First console read-model projection.
Governance scope: minimum product console panels, approval visibility,
    side-effect visibility, verification summaries, receipt bundle, and controls.
Dependencies: OCF runtime contracts, OCF runtime core, and read-model projector.
Invariants:
  - The projection is read-only and carries no execution authority.
  - All minimum console panels are present.
  - Verification and receipt claims remain separate from tool success.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.operator_console_first import (
    ConsoleEpisodeStatus,
    ConsoleFinalStatus,
    ConsoleIntentClass,
    ConsolePlannedAction,
    GatewayDispatchResult,
    HostileInputBoundary,
    RecoveryClass,
    SideEffectManifest,
    StateSnapshot,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.operator_console_first import (
    OperatorConsoleFirstRuntime,
    compute_plan_hash,
)
from mcoi_runtime.core.operator_console_first_read_model import (
    PANEL_KEYS,
    build_operator_console_read_model,
)


_NOW = "2026-06-30T12:00:00Z"
_FUTURE = "2026-06-30T12:30:00Z"


class _Gateway:
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


def _episode(intent_class: ConsoleIntentClass = ConsoleIntentClass.OBSERVE):
    return _runtime().capture_episode(
        operator_id="operator-1",
        raw_request="inspect current task before execution",
        intent_class=intent_class,
        governed_goal={"objective": "prove console state"},
        scope={"target": "local"},
        snapshot=_snapshot(),
    )


def _action(
    *,
    action_id: str = "act-read",
    intent_class: ConsoleIntentClass = ConsoleIntentClass.OBSERVE,
    risk_score: int = 10,
    effects: tuple[str, ...] = ("state_read",),
    side_effects: SideEffectManifest | None = None,
    recovery_class: RecoveryClass = RecoveryClass.R0_NONE,
    recovery_ref: str = "",
    hostile_input_boundary: HostileInputBoundary | None = None,
) -> ConsolePlannedAction:
    return ConsolePlannedAction(
        action_id=action_id,
        capability_id="capability.local.observe",
        intent_class=intent_class,
        risk_score=risk_score,
        expected_effects=effects,
        side_effects_declared=True,
        side_effects=side_effects or SideEffectManifest(reads_data=True),
        recovery_class=recovery_class,
        recovery_plan_ref=recovery_ref,
        evidence_required=("receipt",),
        hostile_input_boundary=hostile_input_boundary or HostileInputBoundary(),
    )


def test_read_model_projects_minimum_console_panels_for_waiting_approval() -> None:
    action = _action(
        action_id="act-send",
        intent_class=ConsoleIntentClass.EXTERNAL_IRREVERSIBLE,
        risk_score=60,
        effects=("message_sent",),
        side_effects=SideEffectManifest(sends_external_data=True, uses_network=True),
        recovery_class=RecoveryClass.R2_COMPENSATING_ACTION,
        recovery_ref="recovery://send-correction",
    )
    episode = _runtime().plan_episode(_episode(ConsoleIntentClass.EXTERNAL_IRREVERSIBLE), (action,))

    read_model = build_operator_console_read_model(episode, generated_at=_NOW)
    panels = read_model["panels"]

    assert read_model["panel_keys"] == list(PANEL_KEYS)
    assert set(panels) == set(PANEL_KEYS)
    assert read_model["projection_only"] is True
    assert read_model["execution_authority"] is False
    assert panels["current_task"]["intent_class"] == "external_irreversible"
    assert panels["state_snapshot"]["state_hash"] == "state-abc"
    assert panels["proposed_plan"]["plan_hash"] == compute_plan_hash((action,))
    assert panels["proposed_plan"]["approval_needed"] is True
    assert panels["risk_and_side_effects"]["max_risk_score"] == 60
    assert panels["approval_lease"]["present"] is False
    assert panels["controlled_execution_log"]["event_count"] == 3
    assert panels["verification_result"]["present"] is False
    assert panels["receipt_bundle"]["present"] is False
    assert panels["controls"]["can_approve"] is True
    assert panels["controls"]["control_execution_authority"] is False
    assert episode.status is ConsoleEpisodeStatus.WAITING_APPROVAL
    assert "approval_required" in read_model["attention"]
    assert "approval_lease_missing" in read_model["attention"]


def test_read_model_projects_unverified_receipt_and_retry_control() -> None:
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
    final_episode, receipt = runtime.execute_episode(
        episode,
        gateway=_Gateway(
            GatewayDispatchResult(
                action_id=action.action_id,
                tool_success=True,
                observed_effects=("draft_created",),
                evidence_refs=(),
            )
        ),
    )

    read_model = build_operator_console_read_model(final_episode, receipt=receipt, generated_at=_NOW)
    panels = read_model["panels"]

    assert receipt.final_status is ConsoleFinalStatus.UNVERIFIED_SUCCESS
    assert read_model["final_status"] == "unverified_success"
    assert panels["verification_result"]["present"] is True
    assert panels["verification_result"]["verified_count"] == 0
    assert panels["verification_result"]["unverified_count"] == 1
    assert panels["verification_result"]["mismatch_count"] == 1
    assert panels["receipt_bundle"]["receipt_id"] == receipt.receipt_id
    assert panels["receipt_bundle"]["unverified_claims"] == ["independent_evidence_missing"]
    assert panels["controls"]["can_retry"] is True
    assert panels["controls"]["can_rollback"] is True
    assert panels["controls"]["rollback_action_ids"] == ["act-draft"]
    assert "independent_evidence_missing" in read_model["attention"]
    assert read_model["receipt_attached"] is True


def test_read_model_surfaces_hostile_input_block_and_policy_controls() -> None:
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
    final_episode, receipt = runtime.execute_episode(
        episode,
        gateway=_Gateway(
            GatewayDispatchResult(
                action_id=action.action_id,
                tool_success=True,
                observed_effects=("state_read",),
                evidence_refs=("evidence://unused",),
            )
        ),
    )

    read_model = build_operator_console_read_model(final_episode, receipt=receipt, generated_at=_NOW)
    panels = read_model["panels"]
    risk_action = panels["risk_and_side_effects"]["actions"][0]

    assert final_episode.status is ConsoleEpisodeStatus.POLICY_DENIED
    assert receipt.final_status is ConsoleFinalStatus.BLOCKED
    assert panels["risk_and_side_effects"]["hostile_input_action_ids"] == ["act-hostile-doc"]
    assert risk_action["hostile_input_blocks_dispatch"] is True
    assert risk_action["hostile_input_boundary"]["external_content_refs"] == [
        "doc://untrusted/comment-1"
    ]
    assert panels["receipt_bundle"]["actions_blocked"] == ["act-hostile-doc"]
    assert panels["controls"]["can_retry"] is True
    assert panels["controls"]["can_rollback"] is False
    assert "blocked" in read_model["attention"]
    assert "hostile_input_authority_violation" in read_model["attention"]


def test_read_model_rejects_cross_episode_receipt() -> None:
    runtime = _runtime()
    first_action = _action(action_id="act-first")
    second_action = _action(action_id="act-second")
    first_episode = runtime.plan_episode(
        runtime.capture_episode(
            operator_id="operator-1",
            raw_request="inspect first episode",
            intent_class=ConsoleIntentClass.OBSERVE,
            governed_goal={"objective": "prove first state"},
            scope={"target": "local"},
            snapshot=_snapshot(),
        ),
        (first_action,),
    )
    second_episode = runtime.plan_episode(_episode(), (second_action,))
    _closed_episode, second_receipt = runtime.execute_episode(
        second_episode,
        gateway=_Gateway(
            GatewayDispatchResult(
                action_id=second_action.action_id,
                tool_success=True,
                observed_effects=("state_read",),
                evidence_refs=("evidence://state-read",),
            )
        ),
    )

    with pytest.raises(RuntimeCoreInvariantError, match="episode_id mismatch"):
        build_operator_console_read_model(first_episode, receipt=second_receipt, generated_at=_NOW)
