"""Purpose: tests for compensation assurance after unresolved effects.
Governance scope: compensation planning, dispatch observation, verification,
reconciliation, and graph anchoring.
Invariants:
  - Compensation is admitted only for unresolved original reconciliation.
  - Compensation succeeds only when compensation effects reconcile to MATCH.
  - Compensation outcomes carry evidence and graph witnesses.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.compensation import CompensationKind, CompensationStatus
from mcoi_runtime.contracts.effect_assurance import ExpectedEffect, ReconciliationStatus
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.graph import NodeType
from mcoi_runtime.core.compensation import CompensationAssuranceGate
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.operational_graph import OperationalGraph


def _clock():
    counter = [0]

    def now() -> str:
        value = counter[0]
        counter[0] += 1
        return f"2026-04-24T14:00:{value:02d}+00:00"

    return now


def _original_context(*effects: EffectRecord):
    clock = _clock()
    graph = OperationalGraph(clock=clock)
    effect_gate = EffectAssuranceGate(clock=clock, graph=graph)
    original_plan = effect_gate.create_plan(
        command_id="cmd-comp-1",
        tenant_id="tenant-1",
        capability_id="financial.payment",
        expected_effects=(
            ExpectedEffect(
                effect_id="ledger_entry_created",
                name="ledger_entry_created",
                target_ref="ledger:tenant-1",
                required=True,
                verification_method="ledger_lookup",
            ),
        ),
        forbidden_effects=("duplicate_payment",),
        compensation_plan_id="financial.refund",
    )
    original_result = ExecutionResult(
        execution_id="exec-original-1",
        goal_id="cmd-comp-1",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=effects,
        assumed_effects=(),
        started_at="2026-04-24T14:00:00+00:00",
        finished_at="2026-04-24T14:00:01+00:00",
        metadata={"tenant_id": "tenant-1"},
    )
    observed = effect_gate.observe(original_result)
    verification = effect_gate.verify(
        plan=original_plan,
        execution_result=original_result,
        observed_effects=observed,
    )
    original_reconciliation = effect_gate.reconcile(
        plan=original_plan,
        observed_effects=observed,
        verification_result=verification,
        case_id="case-comp-1",
    )
    compensation_gate = CompensationAssuranceGate(clock=clock, effect_gate=effect_gate, graph=graph)
    return clock, graph, compensation_gate, original_plan, original_reconciliation


def _successful_refund_dispatch(plan):
    return ExecutionResult(
        execution_id="exec-refund-1",
        goal_id=plan.command_id,
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=(
            EffectRecord(
                name="refund_receipt_received",
                details={
                    "effect_id": "refund_receipt_received",
                    "evidence_ref": "refund:receipt-1",
                    "source": "provider",
                },
            ),
        ),
        assumed_effects=(),
        started_at="2026-04-24T14:01:00+00:00",
        finished_at="2026-04-24T14:01:01+00:00",
        metadata={"tenant_id": "tenant-1"},
    )


def _failed_refund_dispatch(plan):
    return ExecutionResult(
        execution_id="exec-refund-2",
        goal_id=plan.command_id,
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=(
            EffectRecord(
                name="refund_provider_request_created",
                details={
                    "effect_id": "refund_provider_request_created",
                    "evidence_ref": "refund:request-1",
                    "source": "provider",
                },
            ),
        ),
        assumed_effects=(),
        started_at="2026-04-24T14:01:00+00:00",
        finished_at="2026-04-24T14:01:01+00:00",
        metadata={"tenant_id": "tenant-1"},
    )


def test_create_plan_rejects_matched_original_reconciliation():
    _, _, compensation_gate, original_plan, reconciliation = _original_context(
        EffectRecord(name="ledger_entry_created", details={"evidence_ref": "ledger:entry-1"})
    )
    assert reconciliation.status is ReconciliationStatus.MATCH
    with pytest.raises(RuntimeCoreInvariantError, match="unresolved reconciliation"):
        compensation_gate.create_plan(
            original_plan=original_plan,
            original_reconciliation=reconciliation,
            capability_id="financial.refund",
            approval_id="approval-comp-1",
            expected_effects=("refund_receipt_received",),
            forbidden_effects=("duplicate_refund",),
            evidence_required=("refund_id",),
            kind=CompensationKind.COMPENSATION,
        )


def test_successful_compensation_requires_reconciled_compensation_effects():
    _, _, compensation_gate, original_plan, reconciliation = _original_context(
        EffectRecord(name="payment_receipt_received", details={"evidence_ref": "payment:receipt-1"})
    )
    plan = compensation_gate.create_plan(
        original_plan=original_plan,
        original_reconciliation=reconciliation,
        capability_id="financial.refund",
        approval_id="approval-comp-1",
        expected_effects=("refund_receipt_received",),
        forbidden_effects=("duplicate_refund",),
        evidence_required=("refund_id",),
        kind=CompensationKind.COMPENSATION,
    )
    attempt, outcome = compensation_gate.execute(plan, dispatch=_successful_refund_dispatch)
    assert attempt.compensation_plan_id == plan.compensation_plan_id
    assert outcome.status is CompensationStatus.SUCCEEDED
    assert outcome.case_id is None
    assert outcome.evidence_refs == ("refund:receipt-1",)


def test_failed_compensation_requires_review_and_preserves_case():
    _, _, compensation_gate, original_plan, reconciliation = _original_context(
        EffectRecord(name="payment_receipt_received", details={"evidence_ref": "payment:receipt-1"})
    )
    plan = compensation_gate.create_plan(
        original_plan=original_plan,
        original_reconciliation=reconciliation,
        capability_id="financial.refund",
        approval_id="approval-comp-1",
        expected_effects=("refund_receipt_received",),
        forbidden_effects=("duplicate_refund",),
        evidence_required=("refund_id",),
    )
    attempt, outcome = compensation_gate.execute(plan, dispatch=_failed_refund_dispatch)
    assert attempt.evidence_refs == ("refund:request-1",)
    assert outcome.status is CompensationStatus.REQUIRES_REVIEW
    assert outcome.case_id == "case-comp-1"
    assert compensation_gate.outcome_count == 1


def test_compensation_graph_anchor_records_approval_attempt_outcome_and_evidence():
    _, graph, compensation_gate, original_plan, reconciliation = _original_context(
        EffectRecord(name="payment_receipt_received", details={"evidence_ref": "payment:receipt-1"})
    )
    plan = compensation_gate.create_plan(
        original_plan=original_plan,
        original_reconciliation=reconciliation,
        capability_id="financial.refund",
        approval_id="approval-comp-1",
        expected_effects=("refund_receipt_received",),
        forbidden_effects=("duplicate_refund",),
        evidence_required=("refund_id",),
    )
    attempt, outcome = compensation_gate.execute(plan, dispatch=_successful_refund_dispatch)
    nodes = graph.all_nodes()
    assert any(node.node_id == f"compensation_plan:{plan.compensation_plan_id}" for node in nodes)
    assert any(node.node_id == f"compensation_attempt:{attempt.attempt_id}" for node in nodes)
    assert any(node.node_id == f"compensation_outcome:{outcome.outcome_id}" for node in nodes)
    assert any(node.node_id == "approval:approval-comp-1" and node.node_type is NodeType.APPROVAL for node in nodes)
    assert any(node.node_id == "evidence:refund:receipt-1" for node in nodes)
