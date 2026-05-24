"""Purpose: tests for the effect assurance gate.
Governance scope: pre-dispatch planning, simulation, observation, verification,
reconciliation, and graph commit.
Dependencies: effect assurance core, execution contracts, operational graph.
Invariants:
  - Observation reads actual effects only.
  - Reconciliation MATCH is required before graph commit.
  - Simulation verdicts are generated through the read-only simulation engine.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.effect_assurance import ExpectedEffect, ReconciliationStatus
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.graph import NodeType
from mcoi_runtime.contracts.simulation import RiskLevel, VerdictType
from mcoi_runtime.contracts.verification import VerificationStatus
from mcoi_runtime.core import effect_assurance as effect_assurance_module
from mcoi_runtime.core.effect_assurance import (
    EffectAssuranceGate,
    EffectGraphCommitReceiptStore,
    InMemoryEffectGraphCommitReceiptStore,
    JsonlEffectGraphCommitReceiptStore,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.operational_graph import OperationalGraph


def _clock():
    counter = [0]

    def now() -> str:
        value = counter[0]
        counter[0] += 1
        return f"2026-04-24T12:00:{value:02d}+00:00"

    return now


def _expected(effect_id: str = "ledger_entry_created") -> ExpectedEffect:
    return ExpectedEffect(
        effect_id=effect_id,
        name=effect_id,
        target_ref="ledger:tenant-1",
        required=True,
        verification_method="ledger_lookup",
        expected_value={"amount": 300},
    )


def _execution(*effects: EffectRecord) -> ExecutionResult:
    return ExecutionResult(
        execution_id="exec-1",
        goal_id="cmd-1",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=effects,
        assumed_effects=(EffectRecord(name="assumed_side_effect"),),
        started_at="2026-04-24T12:00:00+00:00",
        finished_at="2026-04-24T12:00:01+00:00",
    )


def _graph_commit_receipt():
    store = InMemoryEffectGraphCommitReceiptStore()
    gate, _, plan = _gate_with_plan()
    result = _execution(EffectRecord(name="ledger_entry_created", details={"evidence_ref": "ledger:entry-1"}))
    observed = gate.observe(result)
    verification = gate.verify(plan=plan, execution_result=result, observed_effects=observed)
    reconciliation = gate.reconcile(
        plan=plan,
        observed_effects=observed,
        verification_result=verification,
    )
    receipt = gate.commit_graph(
        plan=plan,
        observed_effects=observed,
        reconciliation=reconciliation,
    )
    store.append(receipt)
    assert store.receipt_count == 1
    return receipt


def _gate_with_plan():
    clock = _clock()
    graph = OperationalGraph(clock=clock)
    gate = EffectAssuranceGate(clock=clock, graph=graph)
    plan = gate.create_plan(
        command_id="cmd-1",
        tenant_id="tenant-1",
        capability_id="send_payment",
        expected_effects=(_expected(),),
        forbidden_effects=("duplicate_payment",),
        compensation_plan_id="refund_payment",
    )
    return gate, graph, plan


def test_create_plan_adds_default_graph_projection_refs():
    gate, _, plan = _gate_with_plan()
    assert plan.effect_plan_id.startswith("effect-plan-")
    assert "command:cmd-1" in plan.graph_node_refs
    assert plan.compensation_plan_id == "refund_payment"
    assert gate is not None


def test_simulate_returns_verdict_without_mutating_graph():
    gate, graph, plan = _gate_with_plan()
    before = graph.capture_snapshot()
    verdict = gate.simulate(plan, risk_level=RiskLevel.LOW)
    after = graph.capture_snapshot()
    assert verdict.verdict_type is VerdictType.PROCEED
    assert before.node_count == after.node_count
    assert before.edge_count == after.edge_count


def test_observe_uses_actual_effects_and_ignores_assumed_effects():
    gate, _, _ = _gate_with_plan()
    result = _execution(
        EffectRecord(
            name="ledger_entry_created",
            details={
                "effect_id": "ledger_entry_created",
                "evidence_ref": "ledger:entry-1",
                "source": "ledger",
                "observed_value": {"amount": 300},
            },
        )
    )
    observed = gate.observe(result)
    assert len(observed) == 1
    assert observed[0].effect_id == "ledger_entry_created"
    assert observed[0].evidence_ref == "ledger:entry-1"
    assert observed[0].name != "assumed_side_effect"


def test_observe_rejects_missing_actual_effects():
    gate, _, _ = _gate_with_plan()
    with pytest.raises(RuntimeCoreInvariantError, match="actual_effects"):
        gate.observe(_execution())


def test_verify_and_reconcile_match_for_expected_effect():
    gate, _, plan = _gate_with_plan()
    result = _execution(EffectRecord(name="ledger_entry_created", details={"evidence_ref": "ledger:entry-1"}))
    observed = gate.observe(result)
    verification = gate.verify(plan=plan, execution_result=result, observed_effects=observed)
    reconciliation = gate.reconcile(plan=plan, observed_effects=observed, verification_result=verification)
    assert verification.status is VerificationStatus.PASS
    assert reconciliation.status is ReconciliationStatus.MATCH
    assert reconciliation.matched_effects == ("ledger_entry_created",)


def test_reconcile_partial_match_for_missing_required_effect():
    gate, _, plan = _gate_with_plan()
    result = _execution(EffectRecord(name="payment_receipt_received", details={"evidence_ref": "receipt:1"}))
    observed = gate.observe(result)
    verification = gate.verify(plan=plan, execution_result=result, observed_effects=observed)
    reconciliation = gate.reconcile(plan=plan, observed_effects=observed, verification_result=verification)
    assert verification.status is VerificationStatus.FAIL
    assert reconciliation.status is ReconciliationStatus.MISMATCH
    assert reconciliation.missing_effects == ("ledger_entry_created",)


def test_reconcile_mismatch_for_forbidden_effect():
    gate, _, plan = _gate_with_plan()
    result = _execution(EffectRecord(name="duplicate_payment", details={"evidence_ref": "provider:dup"}))
    observed = gate.observe(result)
    verification = gate.verify(plan=plan, execution_result=result, observed_effects=observed)
    reconciliation = gate.reconcile(plan=plan, observed_effects=observed, verification_result=verification)
    assert verification.status is VerificationStatus.FAIL
    assert reconciliation.status is ReconciliationStatus.MISMATCH
    assert reconciliation.unexpected_effects == ("duplicate_payment",)


def test_graph_commit_requires_match():
    gate, _, plan = _gate_with_plan()
    result = _execution(EffectRecord(name="duplicate_payment", details={"evidence_ref": "provider:dup"}))
    observed = gate.observe(result)
    verification = gate.verify(plan=plan, execution_result=result, observed_effects=observed)
    reconciliation = gate.reconcile(plan=plan, observed_effects=observed, verification_result=verification)
    with pytest.raises(RuntimeCoreInvariantError, match="MATCH"):
        gate.commit_graph(plan=plan, observed_effects=observed, reconciliation=reconciliation)


def test_graph_commit_writes_command_verification_and_evidence_nodes():
    gate, graph, plan = _gate_with_plan()
    result = _execution(EffectRecord(name="ledger_entry_created", details={"evidence_ref": "ledger:entry-1"}))
    observed = gate.observe(result)
    verification = gate.verify(plan=plan, execution_result=result, observed_effects=observed)
    reconciliation = gate.reconcile(plan=plan, observed_effects=observed, verification_result=verification)
    receipt = gate.commit_graph(plan=plan, observed_effects=observed, reconciliation=reconciliation)
    nodes = graph.all_nodes()
    assert any(node.node_id == "command:cmd-1" for node in nodes)
    assert any(node.node_type is NodeType.VERIFICATION for node in nodes)
    assert any(node.node_id == "evidence:ledger:entry-1" for node in nodes)
    assert receipt.effect_name == "effect_graph_committed"
    assert receipt.command_id == "cmd-1"
    assert receipt.effect_plan_id == plan.effect_plan_id
    assert receipt.reconciliation_id == reconciliation.reconciliation_id
    assert receipt.observed_effect_ids == ("ledger_entry_created",)
    assert receipt.observed_evidence_refs == ("ledger:entry-1",)
    assert receipt.before_node_count == 0
    assert receipt.before_edge_count == 0
    assert receipt.after_node_count >= 4
    assert receipt.after_edge_count >= 4
    assert receipt.metadata["node_delta"] == receipt.after_node_count
    assert receipt.metadata["edge_delta"] == receipt.after_edge_count


def test_graph_commit_receipts_convert_to_effect_records():
    gate, _, plan = _gate_with_plan()
    result = _execution(EffectRecord(name="ledger_entry_created", details={"evidence_ref": "ledger:entry-1"}))
    observed = gate.observe(result)
    verification = gate.verify(plan=plan, execution_result=result, observed_effects=observed)
    reconciliation = gate.reconcile(plan=plan, observed_effects=observed, verification_result=verification)

    receipt = gate.commit_graph(plan=plan, observed_effects=observed, reconciliation=reconciliation)
    effect = gate.graph_commit_effect_records(limit=1)[0]

    assert gate.graph_commit_receipts(limit=1) == (receipt,)
    assert effect.name == "effect_graph_committed"
    assert effect.details["source"] == "effect_assurance_graph_commit"
    assert effect.details["evidence_ref"].startswith("effect-graph-commit:")
    assert effect.details["command_id"] == "cmd-1"
    assert effect.details["observed_effect_ids"] == ("ledger_entry_created",)


def test_graph_commit_receipt_closes_effect_assurance():
    gate, _, plan = _gate_with_plan()
    result = _execution(EffectRecord(name="ledger_entry_created", details={"evidence_ref": "ledger:entry-1"}))
    observed = gate.observe(result)
    verification = gate.verify(plan=plan, execution_result=result, observed_effects=observed)
    reconciliation = gate.reconcile(plan=plan, observed_effects=observed, verification_result=verification)
    gate.commit_graph(plan=plan, observed_effects=observed, reconciliation=reconciliation)
    commit_plan = gate.create_plan(
        command_id="cmd-graph-commit",
        tenant_id="tenant-1",
        capability_id="effect_assurance.commit_graph",
        expected_effects=(
            ExpectedEffect(
                effect_id="effect_graph_committed",
                name="effect_graph_committed",
                target_ref="graph:cmd-1",
                required=True,
                verification_method="effect_graph_commit_receipt",
            ),
        ),
        forbidden_effects=("effect_graph_commit_without_match",),
    )
    commit_execution = ExecutionResult(
        execution_id="exec-graph-commit",
        goal_id="cmd-graph-commit",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=gate.graph_commit_effect_records(limit=1),
        assumed_effects=(),
        started_at="2026-04-24T12:00:00+00:00",
        finished_at="2026-04-24T12:00:01+00:00",
    )

    commit_observed = gate.observe(commit_execution)
    commit_verification = gate.verify(
        plan=commit_plan,
        execution_result=commit_execution,
        observed_effects=commit_observed,
    )
    commit_reconciliation = gate.reconcile(
        plan=commit_plan,
        observed_effects=commit_observed,
        verification_result=commit_verification,
    )

    assert commit_reconciliation.status is ReconciliationStatus.MATCH
    assert commit_reconciliation.matched_effects == ("effect_graph_committed",)
    assert commit_verification.evidence[0].uri.startswith("effect-graph-commit:")


def test_graph_commit_receipt_store_base_is_noop():
    store = EffectGraphCommitReceiptStore()
    gate, _, plan = _gate_with_plan()
    result = _execution(EffectRecord(name="ledger_entry_created", details={"evidence_ref": "ledger:entry-1"}))
    observed = gate.observe(result)
    verification = gate.verify(plan=plan, execution_result=result, observed_effects=observed)
    reconciliation = gate.reconcile(plan=plan, observed_effects=observed, verification_result=verification)
    receipt = gate.commit_graph(plan=plan, observed_effects=observed, reconciliation=reconciliation)

    store.append(receipt)

    assert store.receipt_count == 0
    assert store.list(limit=1) == ()
    assert receipt.receipt_id.startswith("effect-graph-commit-receipt-")


def test_in_memory_graph_commit_receipt_store_bounds_recent_records():
    gate, _, plan = _gate_with_plan()
    first_result = _execution(EffectRecord(name="ledger_entry_created", details={"evidence_ref": "ledger:entry-1"}))
    first_observed = gate.observe(first_result)
    first_verification = gate.verify(plan=plan, execution_result=first_result, observed_effects=first_observed)
    first_reconciliation = gate.reconcile(
        plan=plan,
        observed_effects=first_observed,
        verification_result=first_verification,
    )
    first_receipt = gate.commit_graph(
        plan=plan,
        observed_effects=first_observed,
        reconciliation=first_reconciliation,
    )
    second_receipt = gate.commit_graph(
        plan=plan,
        observed_effects=first_observed,
        reconciliation=first_reconciliation,
    )
    store = InMemoryEffectGraphCommitReceiptStore(max_records=1)

    store.append(first_receipt)
    store.append(second_receipt)

    assert store.receipt_count == 1
    assert store.list(limit=10) == (second_receipt,)
    assert store.list(limit=1)[0].receipt_id == second_receipt.receipt_id


def test_jsonl_graph_commit_receipt_store_replays_records(tmp_path):
    path = tmp_path / "effect-graph-commit-receipts.jsonl"
    store = JsonlEffectGraphCommitReceiptStore(path)
    clock = _clock()
    graph = OperationalGraph(clock=clock)
    gate = EffectAssuranceGate(clock=clock, graph=graph, graph_commit_receipt_store=store)
    plan = gate.create_plan(
        command_id="cmd-1",
        tenant_id="tenant-1",
        capability_id="send_payment",
        expected_effects=(_expected(),),
        forbidden_effects=("duplicate_payment",),
    )
    result = _execution(EffectRecord(name="ledger_entry_created", details={"evidence_ref": "ledger:entry-1"}))
    observed = gate.observe(result)
    verification = gate.verify(plan=plan, execution_result=result, observed_effects=observed)
    reconciliation = gate.reconcile(plan=plan, observed_effects=observed, verification_result=verification)
    receipt = gate.commit_graph(plan=plan, observed_effects=observed, reconciliation=reconciliation)

    reopened = JsonlEffectGraphCommitReceiptStore(path)
    replayed = reopened.list(limit=1)[0]

    assert reopened.receipt_count == 1
    assert replayed.receipt_id == receipt.receipt_id
    assert replayed.observed_evidence_refs == ("ledger:entry-1",)
    assert replayed.to_effect_record().details["source"] == "effect_assurance_graph_commit"


def test_jsonl_graph_commit_receipt_store_sync_defaults_off(tmp_path):
    path = tmp_path / "effect-graph-commit-receipts.jsonl"
    store = JsonlEffectGraphCommitReceiptStore(path)
    receipt = _graph_commit_receipt()

    store.append(receipt)

    assert store.sync_on_write is False
    assert store.receipt_count == 1
    assert path.exists()


def test_jsonl_graph_commit_receipt_store_sync_calls_fsync(tmp_path, monkeypatch):
    path = tmp_path / "effect-graph-commit-receipts.jsonl"
    fsync_calls: list[int] = []

    def _record_fsync(file_descriptor: int) -> None:
        fsync_calls.append(file_descriptor)

    monkeypatch.setattr(effect_assurance_module.os, "fsync", _record_fsync)
    store = JsonlEffectGraphCommitReceiptStore(path, sync_on_write=True)
    receipt = _graph_commit_receipt()

    store.append(receipt)

    assert store.sync_on_write is True
    assert len(fsync_calls) == 1
    assert fsync_calls[0] > 0


def test_jsonl_graph_commit_receipt_store_sync_flag_must_be_boolean(tmp_path):
    path = tmp_path / "effect-graph-commit-receipts.jsonl"

    with pytest.raises(ValueError, match="sync_on_write must be a boolean"):
        JsonlEffectGraphCommitReceiptStore(path, sync_on_write="true")  # type: ignore[arg-type]


def test_jsonl_graph_commit_receipt_store_rejects_malformed_records(tmp_path):
    path = tmp_path / "effect-graph-commit-receipts.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed"):
        JsonlEffectGraphCommitReceiptStore(path)
