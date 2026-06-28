"""Tests for operator control tower status receipt validation.

Purpose: prove the dashboard focus receipt validates outside gateway test
startup and rejects hash, authority, focus, and count drift.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_operator_control_tower_status_receipt and the
operator control tower status receipt schema.
Invariants: the receipt is projection-only, hash-bound, source-bound, and
cannot overclaim workflow receipt completion.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from scripts.validate_operator_control_tower_status_receipt import (
    DEFAULT_OUTPUT,
    build_default_operator_control_tower_status_receipt,
    validate_operator_control_tower_status_receipt,
    write_operator_control_tower_status_receipt_validation,
)


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    receipt_path = tmp_path / "operator_control_tower_status_receipt.json"
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


def test_operator_control_tower_status_receipt_validates_and_writes_report(tmp_path: Path) -> None:
    validation = validate_operator_control_tower_status_receipt()
    output_path = tmp_path / "operator-control-tower-status-receipt-validation.json"

    written_path = write_operator_control_tower_status_receipt_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))
    receipt = build_default_operator_control_tower_status_receipt()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.blocker == "sandbox_receipts_incomplete"
    assert validation.focus_id == "sandbox_patch_receipt"
    assert validation.receipt_id.startswith("operator-control-tower-status-")
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "operator_control_tower_status_receipt_validation.json"
    assert receipt["projection_only"] is True
    assert receipt["external_effects_allowed"] is False
    assert receipt["sandbox_to_pr"]["focus"]["action"] == (
        "attach before state, after state, diff, command, and rollback receipt"
    )


def test_operator_control_tower_status_receipt_rejects_authority_overclaim(tmp_path: Path) -> None:
    receipt = build_default_operator_control_tower_status_receipt()
    receipt["projection_only"] = False
    receipt["external_effects_allowed"] = True

    validation = validate_operator_control_tower_status_receipt(receipt_path=_write_payload(tmp_path, receipt))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "projection_only must be true" in serialized_errors
    assert "external_effects_allowed must be false" in serialized_errors


def test_operator_control_tower_status_receipt_rejects_hash_drift(tmp_path: Path) -> None:
    receipt = build_default_operator_control_tower_status_receipt()
    receipt["action_needed"] = "changed after hash"

    validation = validate_operator_control_tower_status_receipt(receipt_path=_write_payload(tmp_path, receipt))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "receipt_hash must match canonical receipt payload" in serialized_errors


def test_operator_control_tower_status_receipt_rejects_focus_drift(tmp_path: Path) -> None:
    receipt = build_default_operator_control_tower_status_receipt()
    sandbox_to_pr = receipt["sandbox_to_pr"]
    assert isinstance(sandbox_to_pr, dict)
    focus = sandbox_to_pr["focus"]
    assert isinstance(focus, dict)
    focus["focus_id"] = "operator_approval"
    focus["blocker"] = "operator_approval_missing"
    focus["action"] = "wrong action"

    validation = validate_operator_control_tower_status_receipt(receipt_path=_write_payload(tmp_path, receipt))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "sandbox_to_pr.focus_id must identify a pending sandbox receipt" in serialized_errors
    assert "sandbox_to_pr.focus.blocker must match sandbox_to_pr.blocker" in serialized_errors
    assert "sandbox_to_pr.focus.action must match sandbox_to_pr.next_action" in serialized_errors


def test_operator_control_tower_status_receipt_rejects_count_overclaim(tmp_path: Path) -> None:
    receipt = build_default_operator_control_tower_status_receipt()
    workflow_run = receipt["workflow_run"]
    assert isinstance(workflow_run, dict)
    workflow_run["receipt_checklist_completed_required_count"] = 7

    validation = validate_operator_control_tower_status_receipt(receipt_path=_write_payload(tmp_path, receipt))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "completed receipt count cannot exceed required count" in serialized_errors
    assert "receipt_hash must match canonical receipt payload" in serialized_errors


def test_operator_control_tower_status_receipt_cli_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "status-receipt-validation.json"
    receipt_path = tmp_path / "status-receipt.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_operator_control_tower_status_receipt.py",
            "--json",
            "--output",
            str(output_path),
            "--write-default-receipt",
            str(receipt_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))
    written_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert '"ok": true' in completed.stdout
    assert written_payload["errors"] == []
    assert written_payload["focus_id"] == "sandbox_patch_receipt"
    assert written_receipt["receipt_type"] == "operator_control_tower_status_receipt.v1"
    assert written_receipt["receipt_id"].startswith("operator-control-tower-status-")
