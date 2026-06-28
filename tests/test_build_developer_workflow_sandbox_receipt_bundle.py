"""Tests for Developer Workflow sandbox receipt bundle builder.

Purpose: prove explicit local receipt evidence can produce a validated sandbox
receipt bundle without running effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_developer_workflow_sandbox_receipt_bundle and the
sandbox receipt bundle validator.
Invariants: missing evidence remains pending, complete evidence is concrete,
and unknown or incomplete receipt evidence fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_developer_workflow_sandbox_receipt_bundle import (
    DEFAULT_EVIDENCE,
    build_developer_workflow_sandbox_receipt_bundle,
    main,
    write_developer_workflow_sandbox_receipt_bundle,
)
from scripts.validate_developer_workflow_sandbox_receipt_bundle import (
    EXPECTED_RECEIPTS,
    validate_developer_workflow_sandbox_receipt_bundle,
)


def _complete_receipt_evidence(receipt_id: str) -> dict[str, object]:
    return {
        "before_state_hash": f"sha256:before-{receipt_id}",
        "after_state_hash": f"sha256:after-{receipt_id}",
        "diff_hash": f"sha256:diff-{receipt_id}",
        "rollback_command": f"rollback {receipt_id}",
        "command": f"build {receipt_id}",
        "evidence_refs": [f"proof://developer-workflow-v1/{receipt_id}"],
    }


def test_builder_creates_valid_partial_bundle_from_fixture(tmp_path: Path) -> None:
    evidence = json.loads(DEFAULT_EVIDENCE.read_text(encoding="utf-8"))

    bundle = build_developer_workflow_sandbox_receipt_bundle(evidence)
    bundle_path = write_developer_workflow_sandbox_receipt_bundle(bundle, tmp_path / "bundle.json")
    validation = validate_developer_workflow_sandbox_receipt_bundle(bundle_path=bundle_path)

    receipts = {receipt["receipt_id"]: receipt for receipt in bundle["receipts"]}
    assert validation.ok is True
    assert bundle["bundle_status"] == "awaiting_receipts"
    assert bundle["completed_count"] == 1
    assert receipts["sandbox_patch_receipt"]["status"] == "complete"
    assert receipts["test_gate_receipt"]["status"] == "pending"
    assert receipts["test_gate_receipt"]["diff_hash"] == "pending"


def test_builder_creates_valid_complete_bundle(tmp_path: Path) -> None:
    evidence = {
        "workflow_run_id": "developer_workflow_v1_complete_run",
        "receipts": {
            receipt_id: _complete_receipt_evidence(receipt_id)
            for receipt_id, _, _ in EXPECTED_RECEIPTS
        },
    }

    bundle = build_developer_workflow_sandbox_receipt_bundle(evidence)
    bundle_path = write_developer_workflow_sandbox_receipt_bundle(bundle, tmp_path / "bundle.json")
    validation = validate_developer_workflow_sandbox_receipt_bundle(bundle_path=bundle_path)

    assert validation.ok is True
    assert bundle["workflow_run_id"] == "developer_workflow_v1_complete_run"
    assert bundle["bundle_status"] == "receipts_complete"
    assert bundle["completed_count"] == 4
    assert all(receipt["status"] == "complete" for receipt in bundle["receipts"])


def test_builder_rejects_unknown_receipt_id() -> None:
    evidence = {"receipts": {"other_receipt": _complete_receipt_evidence("other_receipt")}}

    with pytest.raises(ValueError, match="unknown_receipt_id:other_receipt"):
        build_developer_workflow_sandbox_receipt_bundle(evidence)


def test_builder_rejects_incomplete_complete_receipt_evidence() -> None:
    evidence = {
        "receipts": {
            "sandbox_patch_receipt": {
                "before_state_hash": "pending",
                "after_state_hash": "sha256:after",
                "diff_hash": "sha256:diff",
                "rollback_command": "rollback",
                "command": "command",
                "evidence_refs": ["proof://receipt"],
            }
        }
    }

    with pytest.raises(ValueError, match="sandbox_patch_receipt.before_state_hash_required"):
        build_developer_workflow_sandbox_receipt_bundle(evidence)


def test_builder_cli_writes_valid_bundle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_path = tmp_path / "generated-bundle.json"

    exit_code = main(["--evidence", str(DEFAULT_EVIDENCE), "--output", str(output_path), "--json"])
    captured = capsys.readouterr()
    validation = validate_developer_workflow_sandbox_receipt_bundle(bundle_path=output_path)

    assert exit_code == 0
    assert output_path.exists()
    assert validation.ok is True
    assert '"bundle_status": "awaiting_receipts"' in captured.out
