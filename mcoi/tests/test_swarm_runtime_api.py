"""Tests for the governed invoice swarm runtime entry point.

Purpose: verify framework-neutral run, lookup, listing, and rejection envelopes
for the invoice swarm capability.
Governance scope: request validation, append-only persistence, proof readback,
and explicit error reporting.
Dependencies: mcoi_runtime.swarm.runtime_api.
Invariants: every accepted run persists one audit record, invalid input is
rejected, and lookup performs no mutation.
"""

from __future__ import annotations

from mcoi_runtime.swarm import InvoiceSwarmRuntime


def _payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "run_id": "run_api_invoice_001",
        "goal_id": "goal_api_invoice_001",
        "tenant_id": "tenant_a",
        "invoice_ref": "invoice_api_001",
        "invoice_amount_usd": "100.25",
        "vendor_verified": True,
        "duplicate_found": False,
        "budget_available": True,
        "policy_requires_approval": True,
        "human_approved": True,
    }
    value.update(overrides)
    return value


def test_runtime_run_invoice_persists_and_returns_closed_record(tmp_path) -> None:
    runtime = InvoiceSwarmRuntime.from_path(tmp_path / "swarm-runs.jsonl")

    envelope = runtime.run_invoice(_payload()).to_dict()
    lookup = runtime.get_run("run_api_invoice_001").to_dict()

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "closed"
    assert lookup["ok"] is True
    assert lookup["payload"]["record"]["proof_stamp"]
    assert runtime.audit_store.count == 1


def test_runtime_rejects_missing_or_invalid_fields_without_persisting(tmp_path) -> None:
    runtime = InvoiceSwarmRuntime.from_path(tmp_path / "swarm-runs.jsonl")

    missing = runtime.run_invoice(_payload(run_id="run_missing", invoice_ref="")).to_dict()
    invalid = runtime.run_invoice(_payload(run_id="run_invalid", vendor_verified="yes")).to_dict()

    assert missing["governed"] is True
    assert missing["ok"] is False
    assert missing["status"] == "rejected"
    assert "invoice_ref" in missing["error"]
    assert invalid["ok"] is False
    assert "vendor_verified" in invalid["error"]
    assert runtime.audit_store.count == 0


def test_runtime_rejects_non_text_run_id_without_persisting(tmp_path) -> None:
    runtime = InvoiceSwarmRuntime.from_path(tmp_path / "swarm-runs.jsonl")

    rejected = runtime.run_invoice(_payload(run_id=1001)).to_dict()
    listed = runtime.list_runs().to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "run_id must be a string" in rejected["error"]
    assert listed["payload"]["count"] == 0
    assert runtime.audit_store.count == 0


def test_runtime_rejects_non_text_symbolic_fields_without_persisting(tmp_path) -> None:
    runtime = InvoiceSwarmRuntime.from_path(tmp_path / "swarm-runs.jsonl")

    goal_rejected = runtime.run_invoice(_payload(run_id="run_bad_goal", goal_id=1001)).to_dict()
    tenant_rejected = runtime.run_invoice(_payload(run_id="run_bad_tenant", tenant_id=False)).to_dict()
    invoice_rejected = runtime.run_invoice(_payload(run_id="run_bad_invoice", invoice_ref=1001)).to_dict()
    listed = runtime.list_runs().to_dict()

    assert goal_rejected["governed"] is True
    assert goal_rejected["ok"] is False
    assert "goal_id must be a string" in goal_rejected["error"]
    assert tenant_rejected["ok"] is False
    assert "tenant_id must be a string" in tenant_rejected["error"]
    assert invoice_rejected["ok"] is False
    assert "invoice_ref must be a string" in invoice_rejected["error"]
    assert listed["payload"]["count"] == 0
    assert runtime.audit_store.count == 0


def test_runtime_list_runs_and_not_found_lookup_are_read_only(tmp_path) -> None:
    runtime = InvoiceSwarmRuntime.from_path(tmp_path / "swarm-runs.jsonl")
    runtime.run_invoice(_payload(run_id="run_api_invoice_001"))
    runtime.run_invoice(_payload(run_id="run_api_invoice_002", goal_id="goal_api_invoice_002"))

    listed = runtime.list_runs().to_dict()
    missing = runtime.get_run("run_absent").to_dict()

    assert listed["ok"] is True
    assert listed["payload"]["count"] == 2
    assert [record["run_id"] for record in listed["payload"]["records"]] == [
        "run_api_invoice_001",
        "run_api_invoice_002",
    ]
    assert missing["ok"] is False
    assert missing["status"] == "not_found"
    assert runtime.audit_store.count == 2
