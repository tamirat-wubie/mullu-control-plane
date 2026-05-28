"""Tests for governed swarm documentation examples.

Purpose: verify documented invoice payloads remain executable and aligned with
the governed swarm outcome table.
Governance scope: example requests must preserve closure, escalation, and
failure semantics.
Dependencies: docs and examples for governed swarm invoice workflow.
Invariants: examples are valid JSON objects and produce the documented result
classes.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.swarm import InvoiceSwarmRuntime


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "governed_swarm"
DOC = ROOT / "docs" / "governed-swarm-invoice.md"


def _load(name: str) -> dict[str, object]:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def test_documented_examples_execute_with_expected_outcomes(tmp_path) -> None:
    runtime = InvoiceSwarmRuntime.from_path(tmp_path / "swarm-runs.jsonl")

    closed = runtime.run_invoice(_load("invoice_closed.json")).to_dict()
    approval = runtime.run_invoice(_load("invoice_approval_required.json")).to_dict()
    duplicate = runtime.run_invoice(_load("invoice_duplicate_blocked.json")).to_dict()

    assert closed["ok"] is True
    assert closed["status"] == "closed"
    assert closed["payload"]["record"]["proof_stamp"]
    assert approval["ok"] is True
    assert approval["status"] == "not_closed"
    assert approval["payload"]["record"]["decision_verdict"] == "escalate"
    assert duplicate["ok"] is True
    assert duplicate["status"] == "not_closed"
    assert duplicate["payload"]["record"]["decision_verdict"] == "failed"


def test_governed_swarm_doc_references_examples_and_route_contracts() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "invoice_closed.json" in text
    assert "run_invoice_closed_001" in text
    assert "/api/v1/swarm/invoice-runs" in text
    assert "proof_stamp" in text
    assert "No specialist receives side-effect authority" in text
