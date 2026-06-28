"""Tests for PR-preparation approval packet building.

Purpose: prove local sandbox receipt bundles can produce projection-only
approval packets without granting PR creation authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_pr_preparation_approval_packet and packet schema.
Invariants: external PR creation remains forbidden, approval defaults to defer,
and complete bundles only authorize local PR candidate packet preparation.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_pr_preparation_approval_packet import (
    build_pr_preparation_approval_packet,
    main,
    validate_pr_preparation_approval_packet,
)


def _bundle(*, complete: bool) -> dict[str, object]:
    receipts = []
    for receipt_id, label, stage in (
        ("sandbox_patch_receipt", "Sandbox patch receipt", "write_files_in_sandbox"),
        ("test_gate_receipt", "Test gate receipt", "run_tests"),
        ("diff_review_receipt", "Diff review receipt", "show_diff"),
        ("terminal_receipt", "Terminal receipt", "show_receipt"),
    ):
        receipts.append({
            "receipt_id": receipt_id,
            "label": label,
            "status": "complete" if complete else "pending",
            "stage": stage,
            "required": True,
            "source": f"workflow_monitor.metadata.developer_workflow_run.receipt_checklist.{receipt_id}",
            "evidence_refs": [f"proof://{receipt_id}"] if complete else [],
            "before_state_hash": "sha256:before" if complete else "pending",
            "after_state_hash": "sha256:after" if complete else "pending",
            "diff_hash": "sha256:diff" if complete else "pending",
            "rollback_command": "rollback" if complete else "pending",
            "command": "command" if complete else "pending",
        })
    return {
        "bundle_id": "developer_workflow_sandbox_receipt_bundle.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_packet_test",
        "bundle_status": "receipts_complete" if complete else "awaiting_receipts",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "rollback_default": True,
        "required_count": 4,
        "completed_count": 4 if complete else 0,
        "receipts": receipts,
    }


def test_pr_preparation_packet_waits_for_receipts_when_bundle_incomplete(tmp_path: Path) -> None:
    packet = build_pr_preparation_approval_packet(
        sandbox_receipt_bundle=_bundle(complete=False),
        bundle_path=tmp_path / "bundle.json",
    )
    validation = validate_pr_preparation_approval_packet(packet=packet)

    assert validation.ok is True
    assert packet["packet_status"] == "awaiting_receipts"
    assert packet["bundle"]["ready"] is False
    assert packet["external_effects_allowed"] is False
    assert packet["pr_creation_allowed"] is False
    assert "open_external_pr" in packet["forbidden_effects"]


def test_pr_preparation_packet_requests_approval_when_bundle_complete(tmp_path: Path) -> None:
    packet = build_pr_preparation_approval_packet(
        sandbox_receipt_bundle=_bundle(complete=True),
        bundle_path=tmp_path / "bundle.json",
    )
    validation = validate_pr_preparation_approval_packet(packet=packet)

    assert validation.ok is True
    assert packet["packet_status"] == "awaiting_operator_approval"
    assert packet["bundle"]["ready"] is True
    assert packet["authorized_effect_after_approval"] == "prepare_local_pr_candidate_packet"
    assert packet["decision_request"]["allowed_decisions"] == [
        "approve_prepare_pr_candidate",
        "reject",
        "defer",
    ]
    assert packet["decision_request"]["default_decision"] == "defer"
    assert packet["pr_creation_allowed"] is False


def test_pr_preparation_packet_records_local_approval_when_bundle_complete(tmp_path: Path) -> None:
    packet = build_pr_preparation_approval_packet(
        sandbox_receipt_bundle=_bundle(complete=True),
        bundle_path=tmp_path / "bundle.json",
        approval_status="approved",
    )
    validation = validate_pr_preparation_approval_packet(packet=packet)

    assert validation.ok is True
    assert packet["packet_status"] == "approval_recorded"
    assert packet["approval_status"] == "approved"
    assert packet["bundle"]["ready"] is True
    assert packet["authorized_effect_after_approval"] == "prepare_local_pr_candidate_packet"
    assert packet["external_effects_allowed"] is False
    assert packet["pr_creation_allowed"] is False


def test_pr_preparation_packet_validator_rejects_approval_before_receipts_complete(tmp_path: Path) -> None:
    packet = build_pr_preparation_approval_packet(
        sandbox_receipt_bundle=_bundle(complete=False),
        bundle_path=tmp_path / "bundle.json",
    )
    packet["approval_status"] = "approved"
    packet["packet_hash"] = "0" * 64

    validation = validate_pr_preparation_approval_packet(packet=packet)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "approval_requires_complete_receipts" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors


def test_pr_preparation_packet_validator_rejects_external_pr_authority(tmp_path: Path) -> None:
    packet = build_pr_preparation_approval_packet(
        sandbox_receipt_bundle=_bundle(complete=True),
        bundle_path=tmp_path / "bundle.json",
    )
    packet["pr_creation_allowed"] = True
    packet["forbidden_effects"] = ["push_branch", "merge", "deploy", "call_connector"]

    validation = validate_pr_preparation_approval_packet(packet=packet)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "$.pr_creation_allowed: expected const False" in serialized_errors
    assert "missing_forbidden_effect:open_external_pr" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors


def test_pr_preparation_packet_cli_writes_json(tmp_path: Path, capsys) -> None:
    bundle_path = tmp_path / "bundle.json"
    output_path = tmp_path / "packet.json"
    bundle_path.write_text(json.dumps(_bundle(complete=True), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    exit_code = main([
        "--bundle",
        str(bundle_path),
        "--output",
        str(output_path),
        "--approval-status",
        "approved",
        "--json",
    ])
    captured = capsys.readouterr()
    packet = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert packet["packet_status"] == "approval_recorded"
    assert packet["approval_status"] == "approved"
    assert packet["pr_creation_allowed"] is False
    assert '"approve_pr_preparation"' in captured.out
