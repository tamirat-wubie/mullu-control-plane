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
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
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
    gate.commit_graph(plan=plan, observed_effects=observed, reconciliation=reconciliation)
    nodes = graph.all_nodes()
    assert any(node.node_id == "command:cmd-1" for node in nodes)
    assert any(node.node_type is NodeType.VERIFICATION for node in nodes)
    assert any(node.node_id == "evidence:ledger:entry-1" for node in nodes)
