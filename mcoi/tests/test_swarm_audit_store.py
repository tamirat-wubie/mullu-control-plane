"""Tests for governed swarm audit persistence.

Purpose: verify JSONL persistence for invoice swarm records with deterministic
readback, duplicate-run protection, and closure status fidelity.
Governance scope: UWMA witness anchoring and PRS proof readback.
Dependencies: mcoi_runtime.swarm audit records and invoice workflow.
Invariants: closed runs preserve proof stamps, escalated runs do not fake
closure, and duplicate run ids are rejected.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from mcoi_runtime.swarm import SwarmAuditStore, SwarmInvariantViolation, invoice_result_to_audit_record
from mcoi_runtime.swarm.invoice_workflow import InvoiceSwarmRequest, run_invoice_swarm


def _request(**overrides: object) -> InvoiceSwarmRequest:
    values = {
        "goal_id": "goal_invoice_audit_001",
        "tenant_id": "tenant_a",
        "invoice_ref": "invoice_audit_001",
        "invoice_amount_usd": Decimal("320.00"),
        "vendor_verified": True,
        "duplicate_found": False,
        "budget_available": True,
        "policy_requires_approval": True,
        "human_approved": True,
    }
    values.update(overrides)
    return InvoiceSwarmRequest(**values)


def test_audit_store_persists_closed_invoice_run_with_proof_stamp(tmp_path) -> None:
    result = run_invoice_swarm(_request())
    record = invoice_result_to_audit_record(
        run_id="run_invoice_001",
        tenant_id="tenant_a",
        result=result,
        created_at="2026-05-05T12:00:00Z",
    )
    store = SwarmAuditStore(tmp_path / "swarm-runs.jsonl")

    store.append(record)
    loaded = store.get("run_invoice_001")

    assert loaded is not None
    assert store.count == 1
    assert loaded.closure_status == "closed"
    assert loaded.proof_stamp == result.closure.proof_stamp
    assert loaded.payload["mil_program"]["instructions"][-1]["capability"] == "payment.dispatch"


def test_audit_store_rejects_duplicate_run_id(tmp_path) -> None:
    result = run_invoice_swarm(_request())
    record = invoice_result_to_audit_record(
        run_id="run_invoice_duplicate",
        tenant_id="tenant_a",
        result=result,
        created_at="2026-05-05T12:00:00Z",
    )
    store = SwarmAuditStore(tmp_path / "swarm-runs.jsonl")

    store.append(record)

    assert store.count == 1
    assert store.get("run_invoice_duplicate") is not None
    with pytest.raises(SwarmInvariantViolation, match="duplicate swarm run_id"):
        store.append(record)


def test_audit_record_preserves_escalated_not_closed_state(tmp_path) -> None:
    result = run_invoice_swarm(_request(human_approved=False))
    record = invoice_result_to_audit_record(
        run_id="run_invoice_escalated",
        tenant_id="tenant_a",
        result=result,
        created_at="2026-05-05T12:00:00Z",
    )
    store = SwarmAuditStore(tmp_path / "swarm-runs.jsonl")

    store.append(record)
    loaded = store.get("run_invoice_escalated")

    assert loaded is not None
    assert loaded.closure_status == "not_closed"
    assert loaded.proof_stamp == ""
    assert loaded.mil_verification_passed is False
    assert loaded.decision_verdict == "escalate"
