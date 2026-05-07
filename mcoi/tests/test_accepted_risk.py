"""Purpose: tests for accepted-risk closure governance.
Governance scope: residual-risk admission, expiry, closure, and graph anchoring.
Dependencies: accepted-risk core, effect-assurance core, execution contracts.
Invariants:
  - Accepted risk requires unresolved reconciliation and explicit evidence.
  - Matched reconciliations cannot be reclassified as accepted risk.
  - Active accepted-risk records expire when their review window elapses.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.accepted_risk import AcceptedRiskDisposition, AcceptedRiskScope
from mcoi_runtime.contracts.effect_assurance import ExpectedEffect, ReconciliationStatus
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.graph import NodeType
from mcoi_runtime.core.accepted_risk import AcceptedRiskLedger
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.operational_graph import OperationalGraph


def _clock():
    values = [
        "2026-04-24T12:00:00+00:00",
        "2026-04-24T12:00:01+00:00",
        "2026-04-24T12:00:02+00:00",
        "2026-04-24T12:00:03+00:00",
        "2026-04-24T12:00:04+00:00",
        "2026-04-24T12:00:05+00:00",
        "2026-04-24T12:00:06+00:00",
        "2026-04-24T12:00:07+00:00",
        "2026-04-24T12:00:08+00:00",
        "2026-04-24T12:00:09+00:00",
        "2026-04-24T12:00:10+00:00",
    ]

    def now() -> str:
        return values.pop(0) if values else "2026-04-24T12:00:11+00:00"

    return now


def _plan_and_result(*effects: EffectRecord):
    clock = _clock()
    graph = OperationalGraph(clock=clock)
    gate = EffectAssuranceGate(clock=clock, graph=graph)
    plan = gate.create_plan(
        command_id="cmd-risk-1",
        tenant_id="tenant-1",
        capability_id="send_payment",
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
        compensation_plan_id="refund_payment",
    )
    result = ExecutionResult(
        execution_id="exec-risk-1",
        goal_id="cmd-risk-1",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=effects,
        assumed_effects=(),
        started_at="2026-04-24T12:00:00+00:00",
        finished_at="2026-04-24T12:00:01+00:00",
    )
    observed = gate.observe(result)
    verification = gate.verify(plan=plan, execution_result=result, observed_effects=observed)
    reconciliation = gate.reconcile(
        plan=plan,
        observed_effects=observed,
        verification_result=verification,
        case_id="case-risk-1",
    )
    return clock, graph, plan, result, verification, reconciliation


def test_accepts_unresolved_reconciliation_with_owner_evidence_and_expiry():
    clock, _, plan, result, verification, reconciliation = _plan_and_result(
        EffectRecord(name="provider_receipt_received", details={"evidence_ref": "receipt:provider-1"})
    )
    ledger = AcceptedRiskLedger(clock=clock)
    record = ledger.accept(
        plan=plan,
        execution_result=result,
        reconciliation=reconciliation,
        verification_result=verification,
        case_id="case-risk-1",
        reason="ledger observer unavailable during provider-confirmed payment review",
        accepted_by="approver-1",
        owner_id="owner-1",
        expires_at="2026-04-24T13:00:00+00:00",
        review_obligation_id="obl-risk-1",
        evidence_refs=("receipt:provider-1",),
    )
    assert record.scope is AcceptedRiskScope.EFFECT_RECONCILIATION
    assert record.disposition is AcceptedRiskDisposition.ACTIVE
    assert ledger.record_count == 1
    assert record.metadata["reconciliation_status"] == ReconciliationStatus.MISMATCH.value


def test_rejects_accepted_risk_without_evidence_reference():
    clock, _, plan, result, verification, reconciliation = _plan_and_result(
        EffectRecord(name="provider_receipt_received", details={"evidence_ref": "receipt:provider-1"})
    )
    ledger = AcceptedRiskLedger(clock=clock)
    decision = ledger.evaluate_acceptance(
        plan=plan,
        execution_result=result,
        reconciliation=reconciliation,
        verification_result=verification,
        case_id="case-risk-1",
        reason="ledger observer unavailable",
        accepted_by="approver-1",
        owner_id="owner-1",
        expires_at="2026-04-24T13:00:00+00:00",
        review_obligation_id="obl-risk-1",
        evidence_refs=(),
    )
    assert decision.allowed is False
    assert "evidence_refs" in decision.missing_requirements
    assert decision.command_id == plan.command_id
    assert ledger.record_count == 0


def test_rejects_matched_reconciliation_as_accepted_risk():
    clock, _, plan, result, verification, reconciliation = _plan_and_result(
        EffectRecord(name="ledger_entry_created", details={"evidence_ref": "ledger:entry-1"})
    )
    ledger = AcceptedRiskLedger(clock=clock)
    with pytest.raises(RuntimeCoreInvariantError, match="accepted risk requirements missing"):
        ledger.accept(
            plan=plan,
            execution_result=result,
            reconciliation=reconciliation,
            verification_result=verification,
            case_id="case-risk-1",
            reason="not needed",
            accepted_by="approver-1",
            owner_id="owner-1",
            expires_at="2026-04-24T13:00:00+00:00",
            review_obligation_id="obl-risk-1",
            evidence_refs=("ledger:entry-1",),
        )
    assert reconciliation.status is ReconciliationStatus.MATCH
    assert ledger.record_count == 0


def test_expire_due_records_marks_active_record_expired():
    clock, _, plan, result, verification, reconciliation = _plan_and_result(
        EffectRecord(name="provider_receipt_received", details={"evidence_ref": "receipt:provider-1"})
    )
    ledger = AcceptedRiskLedger(clock=clock)
    record = ledger.accept(
        plan=plan,
        execution_result=result,
        reconciliation=reconciliation,
        verification_result=verification,
        case_id="case-risk-1",
        reason="ledger observer unavailable",
        accepted_by="approver-1",
        owner_id="owner-1",
        expires_at="2026-04-24T12:00:06+00:00",
        review_obligation_id="obl-risk-1",
        evidence_refs=("receipt:provider-1",),
    )
    expired = ledger.expire_due_records()
    assert expired[0].risk_id == record.risk_id
    assert expired[0].disposition is AcceptedRiskDisposition.EXPIRED
    assert ledger.get_record(record.risk_id).disposition is AcceptedRiskDisposition.EXPIRED


def test_close_active_record_requires_follow_up_evidence():
    clock, _, plan, result, verification, reconciliation = _plan_and_result(
        EffectRecord(name="provider_receipt_received", details={"evidence_ref": "receipt:provider-1"})
    )
    ledger = AcceptedRiskLedger(clock=clock)
    record = ledger.accept(
        plan=plan,
        execution_result=result,
        reconciliation=reconciliation,
        verification_result=verification,
        case_id="case-risk-1",
        reason="ledger observer unavailable",
        accepted_by="approver-1",
        owner_id="owner-1",
        expires_at="2026-04-24T13:00:00+00:00",
        review_obligation_id="obl-risk-1",
        evidence_refs=("receipt:provider-1",),
    )
    closed = ledger.close(record.risk_id, evidence_ref="ledger:follow-up-1")
    assert closed.disposition is AcceptedRiskDisposition.CLOSED
    assert closed.evidence_refs[-1] == "ledger:follow-up-1"
    assert ledger.get_record(record.risk_id).disposition is AcceptedRiskDisposition.CLOSED
    assert len(closed.evidence_refs) == 2


def test_graph_anchor_records_review_owner_obligation_and_evidence():
    clock, graph, plan, result, verification, reconciliation = _plan_and_result(
        EffectRecord(name="provider_receipt_received", details={"evidence_ref": "receipt:provider-1"})
    )
    ledger = AcceptedRiskLedger(clock=clock, graph=graph)
    record = ledger.accept(
        plan=plan,
        execution_result=result,
        reconciliation=reconciliation,
        verification_result=verification,
        case_id="case-risk-1",
        reason="ledger observer unavailable",
        accepted_by="approver-1",
        owner_id="owner-1",
        expires_at="2026-04-24T13:00:00+00:00",
        review_obligation_id="obl-risk-1",
        evidence_refs=("receipt:provider-1",),
    )
    nodes = graph.all_nodes()
    assert any(node.node_id == f"accepted_risk:{record.risk_id}" for node in nodes)
    assert any(node.node_id == "person:owner-1" and node.node_type is NodeType.PERSON for node in nodes)
    assert any(node.node_id == "obligation:obl-risk-1" for node in nodes)
    assert any(node.node_id == "evidence:receipt:provider-1" for node in nodes)
