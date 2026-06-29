"""Purpose: verify causal repair admission, rollback, compensation, and recovery.
Governance scope: local causal repair engine behavior and receipt evidence.
Dependencies: pytest and mcoi_runtime.core.causal_repair.
Invariants:
  - Risky mutation is blocked without repair evidence.
  - False success triggers verified repair instead of success closure.
  - Unknown commit state blocks blind retry.
  - Duplicate compensation is suppressed by idempotency.
  - Drifted state is escalated instead of overwritten.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.causal_repair import (
    CausalRepairAction,
    CausalRepairEngine,
    CommitState,
    CompensationAdequacyStatus,
    CompensationContract,
    DurableEpisodeState,
    EffectClass,
    InMemoryRepairEpisodeStore,
    ReconciliationContract,
    RepairClosureStatus,
    RepairEngineCrash,
    ReversibilityClass,
    SnapshotQuality,
    SnapshotReceipt,
    UnknownCommitStateError,
)


NOW = "2026-06-29T12:00:00+00:00"


def _clock() -> str:
    return NOW


def _snapshot(action_id: str, quality: SnapshotQuality = SnapshotQuality.S2_LOCAL) -> SnapshotReceipt:
    return SnapshotReceipt(
        snapshot_id=f"snapshot-{action_id}",
        action_id=action_id,
        before_hash=f"before-{action_id}",
        snapshot_quality=quality,
        observed_fields=("value",),
    )


def _compensation(action_id: str, idempotency_key: str = "idem-comp") -> CompensationContract:
    return CompensationContract(
        compensation_id=f"compensation-{action_id}",
        original_action_id=action_id,
        idempotency_key=idempotency_key,
        adequacy_criteria=("truthful_correction", "duplicate_safe", "verified"),
        verification_rule="correction_count_recorded",
        escalation_rule="operator_review",
    )


def test_false_success_triggers_exact_rollback_and_verified_closure() -> None:
    engine = CausalRepairEngine(clock=_clock)

    action = CausalRepairAction(
        action_id="local-edit",
        actor_id="actor-1",
        domain="filesystem",
        target_ref="file://config",
        boundary_scope=("file://config",),
        effect_class=EffectClass.INTERNAL_REVERSIBLE,
        reversibility_class=ReversibilityClass.EXACT_ROLLBACK,
        snapshot_receipt=_snapshot("local-edit"),
        execute=lambda state: {**state, "value": "bad"},
        verify_success=lambda state: state["value"] == "expected",
        rollback=lambda state: {**state, "value": "old", "rolled_back": True},
        verify_repair=lambda state: state["value"] == "old" and state["rolled_back"] is True,
    )

    receipt = engine.run(goal="repair failed local edit", state={"value": "old"}, actions=(action,))

    assert receipt.final_status is RepairClosureStatus.ROLLED_BACK_VERIFIED
    assert receipt.final_state == {"value": "old", "rolled_back": True}
    assert receipt.actions[0].commit_state is CommitState.FAILED_AFTER_COMMIT
    assert receipt.actions[0].repair_status == "exact_rollback_verified"
    assert DurableEpisodeState.REPAIR_REQUIRED in {item.state for item in receipt.durable_receipts}
    assert receipt.unresolved_deltas == []


def test_external_mutation_without_idempotency_is_blocked_before_damage() -> None:
    executed: list[str] = []
    engine = CausalRepairEngine(clock=_clock)
    action = CausalRepairAction(
        action_id="email-send",
        actor_id="actor-1",
        domain="email",
        target_ref="mail://thread-1",
        boundary_scope=("mail://thread-1",),
        effect_class=EffectClass.USER_VISIBLE,
        reversibility_class=ReversibilityClass.SEMANTIC_COMPENSATION,
        compensation_contract=_compensation("email-send"),
        execute=lambda state: executed.append("called") or state,
        verify_success=lambda state: True,
        compensate=lambda state: state,
    )

    receipt = engine.run(goal="send visible email", state={}, actions=(action,))

    assert receipt.final_status is RepairClosureStatus.BLOCKED_BEFORE_DAMAGE
    assert executed == []
    assert receipt.admissions[0].status == "blocked"
    assert receipt.admissions[0].reason == "idempotency_key_missing"
    assert receipt.actions[0].commit_state is CommitState.FAILED_BEFORE_COMMIT
    assert receipt.ledger_hash.startswith("causal-repair-ledger-")


def test_unknown_commit_state_reconciles_without_blind_retry() -> None:
    attempts: list[str] = []
    reconciliations: list[str] = []
    engine = CausalRepairEngine(clock=_clock)

    def execute(state: dict[str, object]) -> dict[str, object]:
        attempts.append("execute")
        raise UnknownCommitStateError("provider timeout after request")

    def reconcile(state: dict[str, object]) -> CommitState:
        reconciliations.append("lookup")
        return CommitState.RECONCILED_SAFE_TO_RETRY

    action = CausalRepairAction(
        action_id="payment-charge",
        actor_id="actor-1",
        domain="payments",
        target_ref="payment://charge-1",
        boundary_scope=("payment://charge-1",),
        effect_class=EffectClass.FINANCIAL_OR_LEGAL,
        reversibility_class=ReversibilityClass.RECONCILE_REQUIRED,
        idempotency_key="idem-payment-charge",
        reconciliation_contract=ReconciliationContract(
            reconciliation_id="reconcile-payment-charge",
            action_id="payment-charge",
            provider_lookup_ref="provider://payments/charges",
            idempotency_lookup_key="idem-payment-charge",
            safe_retry_condition="provider confirms no charge",
            escalation_condition="provider ambiguity remains",
        ),
        execute=execute,
        verify_success=lambda state: True,
        reconcile=reconcile,
    )

    receipt = engine.run(goal="charge payment", state={}, actions=(action,))

    assert attempts == ["execute"]
    assert reconciliations == ["lookup"]
    assert receipt.final_status is RepairClosureStatus.FAILED_UNSAFE_TO_RETRY
    assert receipt.actions[0].commit_state is CommitState.UNKNOWN_COMMIT_STATE
    assert receipt.actions[0].repair_status == "reconciled_safe_to_retry"
    assert receipt.unresolved_deltas == ["payment-charge"]


def test_duplicate_compensation_is_suppressed_by_original_idempotency() -> None:
    engine = CausalRepairEngine(clock=_clock)

    def send_marker(marker: str):
        def execute(state: dict[str, int]) -> dict[str, int]:
            return {**state, marker: state.get(marker, 0) + 1}

        return execute

    def compensate(state: dict[str, int]) -> dict[str, int]:
        return {**state, "corrections": state.get("corrections", 0) + 1}

    shared_compensation = _compensation("email-a", "idem-shared-correction")
    first_action = CausalRepairAction(
        action_id="email-a",
        actor_id="actor-1",
        domain="email",
        target_ref="mail://thread-a",
        boundary_scope=("mail://thread-a",),
        effect_class=EffectClass.USER_VISIBLE,
        reversibility_class=ReversibilityClass.SEMANTIC_COMPENSATION,
        idempotency_key="idem-email-a",
        compensation_contract=shared_compensation,
        execute=send_marker("email_a_sent"),
        verify_success=lambda state: True,
        compensate=compensate,
        verify_repair=lambda state: state.get("corrections", 0) <= 1,
        compensation_adequacy=lambda state: CompensationAdequacyStatus.SEMANTICALLY_ACCEPTABLE,
    )
    second_action = CausalRepairAction(
        action_id="email-b",
        actor_id="actor-1",
        domain="email",
        target_ref="mail://thread-b",
        boundary_scope=("mail://thread-b",),
        effect_class=EffectClass.USER_VISIBLE,
        reversibility_class=ReversibilityClass.SEMANTIC_COMPENSATION,
        idempotency_key="idem-email-b",
        compensation_contract=shared_compensation,
        execute=send_marker("email_b_sent"),
        verify_success=lambda state: False,
        compensate=compensate,
        verify_repair=lambda state: state.get("corrections", 0) <= 1,
        compensation_adequacy=lambda state: CompensationAdequacyStatus.SEMANTICALLY_ACCEPTABLE,
    )

    receipt = engine.run(
        goal="repair visible email chain",
        state={"corrections": 0},
        actions=(first_action, second_action),
    )

    assert receipt.final_status is RepairClosureStatus.SEMANTICALLY_REPAIRED
    assert receipt.final_state["corrections"] == 1
    assert receipt.actions[1].repair_status == "compensation_semantically_acceptable"
    assert receipt.actions[0].repair_status == "duplicate_compensation_suppressed"
    assert receipt.repaired_deltas == ["email-b", "email-a"]
    assert receipt.unresolved_deltas == []


def test_drift_blocks_exact_rollback_before_overwrite() -> None:
    rollback_calls: list[str] = []
    engine = CausalRepairEngine(clock=_clock)
    action = CausalRepairAction(
        action_id="drifted-row-update",
        actor_id="actor-1",
        domain="database",
        target_ref="row://customer-1",
        boundary_scope=("row://customer-1",),
        effect_class=EffectClass.INTERNAL_REVERSIBLE,
        reversibility_class=ReversibilityClass.EXACT_ROLLBACK,
        snapshot_receipt=_snapshot("drifted-row-update"),
        execute=lambda state: {**state, "value": "bad"},
        verify_success=lambda state: False,
        rollback=lambda state: rollback_calls.append("rollback") or state,
        verify_repair=lambda state: True,
        drift_detector=lambda state: True,
    )

    receipt = engine.run(goal="repair drifted row", state={"value": "old"}, actions=(action,))

    assert receipt.final_status is RepairClosureStatus.PARTIALLY_REPAIRED_ESCALATED
    assert rollback_calls == []
    assert receipt.actions[0].repair_status == "drift_detected_escalated"
    assert receipt.unresolved_deltas == ["drifted-row-update"]
    assert receipt.repaired_deltas == []
    assert receipt.final_state == {"value": "bad"}


def test_engine_crash_leaves_recoverable_durable_episode() -> None:
    store = InMemoryRepairEpisodeStore()
    engine = CausalRepairEngine(clock=_clock, store=store)
    action = CausalRepairAction(
        action_id="crashing-observation",
        actor_id="actor-1",
        domain="diagnostics",
        target_ref="probe://local",
        boundary_scope=(),
        effect_class=EffectClass.READ_ONLY,
        reversibility_class=ReversibilityClass.READ_ONLY,
        execute=lambda state: (_ for _ in ()).throw(RepairEngineCrash("process stopped")),
        verify_success=lambda state: True,
    )
    episode_id = engine.build_episode_id(goal="observe crash recovery", actions=(action,))

    with pytest.raises(RepairEngineCrash):
        engine.run(
            goal="observe crash recovery",
            state={},
            actions=(action,),
            episode_id=episode_id,
        )

    durable_states = tuple(receipt.state for receipt in store.list_episode(episode_id))
    assert durable_states == (
        DurableEpisodeState.EPISODE_PREPARED,
        DurableEpisodeState.ACTION_PREPARED,
        DurableEpisodeState.ACTION_ATTEMPTED,
    )
    assert engine.recoverable_episode_ids() == (episode_id,)
    assert store.latest_state(episode_id) is DurableEpisodeState.ACTION_ATTEMPTED
