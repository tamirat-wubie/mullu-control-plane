"""Tests for governed swarm audit persistence.

Purpose: verify JSONL persistence for invoice swarm records with deterministic
readback, duplicate-run protection, and closure status fidelity.
Governance scope: UWMA witness anchoring and PRS proof readback.
Dependencies: mcoi_runtime.swarm audit records and invoice workflow.
Invariants: closed runs preserve proof stamps, escalated runs do not fake
closure, and duplicate run ids are rejected.
"""

from __future__ import annotations

import json
import threading
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


def test_audit_store_serializes_concurrent_duplicate_run_id(tmp_path) -> None:
    # The duplicate-run-id check and the append must be one atomic critical
    # section. Without it, concurrent appends with the same run_id both pass
    # the check and both persist, breaking the append-only-by-run-id invariant.
    result = run_invoice_swarm(_request())
    store = SwarmAuditStore(tmp_path / "swarm-runs.jsonl")

    def _record():
        return invoice_result_to_audit_record(
            run_id="run_invoice_race",
            tenant_id="tenant_a",
            result=result,
            created_at="2026-05-05T12:00:00Z",
        )

    workers = 16
    ready = threading.Barrier(workers)
    outcomes: list[str] = []
    outcomes_lock = threading.Lock()

    def worker() -> None:
        ready.wait()
        try:
            store.append(_record())
            outcome = "ok"
        except SwarmInvariantViolation:
            outcome = "rejected"
        with outcomes_lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count("ok") == 1
    assert outcomes.count("rejected") == workers - 1
    assert store.count == 1


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


def test_audit_store_rejects_non_text_persisted_symbolic_fields(tmp_path) -> None:
    result = run_invoice_swarm(_request())
    record = invoice_result_to_audit_record(
        run_id="run_invoice_corrupt_text",
        tenant_id="tenant_a",
        result=result,
        created_at="2026-05-05T12:00:00Z",
    ).to_dict()
    record["run_id"] = 1001
    store_path = tmp_path / "swarm-runs.jsonl"
    store_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    store = SwarmAuditStore(store_path)

    with pytest.raises(SwarmInvariantViolation, match="invalid audit record at line 1"):
        store.list_records()
    with pytest.raises(SwarmInvariantViolation, match="invalid audit record at line 1"):
        store.get("1001")
    with pytest.raises(SwarmInvariantViolation, match="invalid audit record at line 1"):
        _ = store.count


def test_audit_store_rejects_non_boolean_persisted_proof_flags(tmp_path) -> None:
    result = run_invoice_swarm(_request())
    record = invoice_result_to_audit_record(
        run_id="run_invoice_corrupt_bool",
        tenant_id="tenant_a",
        result=result,
        created_at="2026-05-05T12:00:00Z",
    ).to_dict()
    record["verification_passed"] = "false"
    store_path = tmp_path / "swarm-runs.jsonl"
    store_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    store = SwarmAuditStore(store_path)

    with pytest.raises(SwarmInvariantViolation, match="invalid audit record at line 1"):
        store.list_records()
    with pytest.raises(SwarmInvariantViolation, match="invalid audit record at line 1"):
        store.get("run_invoice_corrupt_bool")
    with pytest.raises(SwarmInvariantViolation, match="invalid audit record at line 1"):
        _ = store.count


def test_audit_store_rejects_non_object_persisted_payload(tmp_path) -> None:
    result = run_invoice_swarm(_request())
    record = invoice_result_to_audit_record(
        run_id="run_invoice_corrupt_payload",
        tenant_id="tenant_a",
        result=result,
        created_at="2026-05-05T12:00:00Z",
    ).to_dict()
    record["payload"] = ["not", "an", "object"]
    store_path = tmp_path / "swarm-runs.jsonl"
    store_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    store = SwarmAuditStore(store_path)

    with pytest.raises(SwarmInvariantViolation, match="invalid audit record at line 1"):
        store.list_records()
    with pytest.raises(SwarmInvariantViolation, match="invalid audit record at line 1"):
        store.get("run_invoice_corrupt_payload")
    with pytest.raises(SwarmInvariantViolation, match="invalid audit record at line 1"):
        _ = store.count
