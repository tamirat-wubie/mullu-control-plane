"""Tests for Developer Workflow operator receipt building.

Purpose: prove the compact operator receipt summarizes the generated Developer
Workflow v1 packet chain without executing external PR effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_developer_workflow_operator_receipt.
Invariants: execution remains false and readiness claims match source packets.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_developer_workflow_operator_receipt import (
    build_developer_workflow_operator_receipt,
    main,
    validate_developer_workflow_operator_receipt,
)
from scripts.build_developer_workflow_sandbox_receipt_bundle import build_developer_workflow_sandbox_receipt_bundle
from scripts.build_external_pr_execution_approval_witness import build_external_pr_execution_approval_witness
from scripts.build_local_pr_candidate_packet import build_local_pr_candidate_packet
from scripts.build_pr_command_preview_packet import build_pr_command_preview_packet
from scripts.build_pr_metadata_packet import build_pr_metadata_packet
from scripts.build_pr_preparation_approval_packet import build_pr_preparation_approval_packet
from scripts.build_pr_readiness_bundle import build_pr_readiness_bundle
from scripts.build_pr_tool_admission_packet import build_pr_tool_admission_packet


def _complete_evidence() -> dict[str, object]:
    receipts = {}
    for receipt_id in ("sandbox_patch_receipt", "test_gate_receipt", "diff_review_receipt", "terminal_receipt"):
        receipts[receipt_id] = {
            "after_state_hash": "sha256:" + "a" * 64,
            "before_state_hash": "sha256:" + "b" * 64,
            "command": f"command for {receipt_id}",
            "diff_hash": "sha256:" + "c" * 64,
            "evidence_refs": [f"proof://{receipt_id}"],
            "rollback_command": f"rollback {receipt_id}",
        }
    return {"workflow_run_id": "developer_workflow_v1_operator_receipt_test", "receipts": receipts}


def _packet_chain(tmp_path: Path, *, local_approved: bool, external_approved: bool) -> dict[str, object]:
    sandbox = build_developer_workflow_sandbox_receipt_bundle(_complete_evidence())
    approval = build_pr_preparation_approval_packet(
        sandbox_receipt_bundle=sandbox,
        bundle_path=tmp_path / "sandbox.json",
        approval_status="approved" if local_approved else "pending",
    )
    candidate = build_local_pr_candidate_packet(
        approval_packet=approval,
        approval_packet_path=tmp_path / "approval.json",
        title="Local candidate",
        branch_name="codex/local-candidate",
        summary="Local candidate summary",
    )
    admission = build_pr_tool_admission_packet(candidate_packet=candidate, candidate_packet_path=tmp_path / "candidate.json")
    witness = build_external_pr_execution_approval_witness(
        admission_packet=admission,
        admission_packet_path=tmp_path / "admission.json",
        approval_status="approved" if external_approved else "pending",
    )
    preview = build_pr_command_preview_packet(approval_witness=witness, approval_witness_path=tmp_path / "witness.json")
    metadata = build_pr_metadata_packet(
        candidate_packet=candidate,
        candidate_packet_path=tmp_path / "candidate.json",
        command_preview_packet=preview,
        command_preview_packet_path=tmp_path / "preview.json",
    )
    readiness = build_pr_readiness_bundle(
        sandbox_receipts=sandbox,
        sandbox_receipts_path=tmp_path / "sandbox.json",
        approval_packet=approval,
        approval_packet_path=tmp_path / "approval.json",
        local_candidate=candidate,
        local_candidate_path=tmp_path / "candidate.json",
        pr_tool_admission=admission,
        pr_tool_admission_path=tmp_path / "admission.json",
        external_witness=witness,
        external_witness_path=tmp_path / "witness.json",
        command_preview=preview,
        command_preview_path=tmp_path / "preview.json",
        metadata=metadata,
        metadata_path=tmp_path / "metadata.json",
    )
    return {
        "sandbox": sandbox,
        "approval": approval,
        "candidate": candidate,
        "admission": admission,
        "witness": witness,
        "preview": preview,
        "metadata": metadata,
        "readiness": readiness,
    }


def test_operator_receipt_summarizes_blocked_chain(tmp_path: Path) -> None:
    chain = _packet_chain(tmp_path, local_approved=False, external_approved=False)
    receipt = build_developer_workflow_operator_receipt(
        sandbox_receipts=chain["sandbox"],
        sandbox_receipts_path=tmp_path / "sandbox.json",
        approval_packet=chain["approval"],
        approval_packet_path=tmp_path / "approval.json",
        local_candidate=chain["candidate"],
        local_candidate_path=tmp_path / "candidate.json",
        pr_tool_admission=chain["admission"],
        pr_tool_admission_path=tmp_path / "admission.json",
        external_witness=chain["witness"],
        external_witness_path=tmp_path / "witness.json",
        command_preview=chain["preview"],
        command_preview_path=tmp_path / "preview.json",
        metadata=chain["metadata"],
        metadata_path=tmp_path / "metadata.json",
        pr_readiness=chain["readiness"],
        pr_readiness_path=tmp_path / "readiness.json",
    )
    validation = validate_developer_workflow_operator_receipt(receipt=receipt)

    assert validation.ok is True
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["execution_performed"] is False
    assert receipt["readiness_status"] == "awaiting_operator_approval"
    assert receipt["external_handoff"]["command_preview_rendered"] is False
    assert receipt["sandbox_receipts"]["completed_count"] == 4


def test_operator_receipt_summarizes_ready_preview_without_execution(tmp_path: Path) -> None:
    chain = _packet_chain(tmp_path, local_approved=True, external_approved=True)
    receipt = build_developer_workflow_operator_receipt(
        sandbox_receipts=chain["sandbox"],
        sandbox_receipts_path=tmp_path / "sandbox.json",
        approval_packet=chain["approval"],
        approval_packet_path=tmp_path / "approval.json",
        local_candidate=chain["candidate"],
        local_candidate_path=tmp_path / "candidate.json",
        pr_tool_admission=chain["admission"],
        pr_tool_admission_path=tmp_path / "admission.json",
        external_witness=chain["witness"],
        external_witness_path=tmp_path / "witness.json",
        command_preview=chain["preview"],
        command_preview_path=tmp_path / "preview.json",
        metadata=chain["metadata"],
        metadata_path=tmp_path / "metadata.json",
        pr_readiness=chain["readiness"],
        pr_readiness_path=tmp_path / "readiness.json",
    )
    validation = validate_developer_workflow_operator_receipt(receipt=receipt)

    assert validation.ok is True
    assert receipt["solver_outcome"] == "SolvedUnverified"
    assert receipt["readiness_status"] == "ready_for_external_pr_execution"
    assert receipt["execution_performed"] is False
    assert receipt["external_handoff"]["command_preview_rendered"] is True
    assert receipt["external_handoff"]["pr_creation_allowed"] is True


def test_operator_receipt_validator_rejects_execution_claim(tmp_path: Path) -> None:
    chain = _packet_chain(tmp_path, local_approved=True, external_approved=True)
    receipt = build_developer_workflow_operator_receipt(
        sandbox_receipts=chain["sandbox"],
        sandbox_receipts_path=tmp_path / "sandbox.json",
        approval_packet=chain["approval"],
        approval_packet_path=tmp_path / "approval.json",
        local_candidate=chain["candidate"],
        local_candidate_path=tmp_path / "candidate.json",
        pr_tool_admission=chain["admission"],
        pr_tool_admission_path=tmp_path / "admission.json",
        external_witness=chain["witness"],
        external_witness_path=tmp_path / "witness.json",
        command_preview=chain["preview"],
        command_preview_path=tmp_path / "preview.json",
        metadata=chain["metadata"],
        metadata_path=tmp_path / "metadata.json",
        pr_readiness=chain["readiness"],
        pr_readiness_path=tmp_path / "readiness.json",
    )
    receipt["execution_performed"] = True

    validation = validate_developer_workflow_operator_receipt(receipt=receipt)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "$.execution_performed: expected const False" in serialized_errors
    assert "execution_performed_must_be_false" in serialized_errors
    assert "receipt_hash_mismatch" in serialized_errors


def test_operator_receipt_cli_writes_json(tmp_path: Path, capsys) -> None:
    chain = _packet_chain(tmp_path, local_approved=True, external_approved=True)
    paths = {}
    for key, payload in chain.items():
        path = tmp_path / f"{key}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths[key] = path
    output_path = tmp_path / "operator-receipt.json"

    exit_code = main([
        "--sandbox-receipts", str(paths["sandbox"]),
        "--approval-packet", str(paths["approval"]),
        "--local-candidate", str(paths["candidate"]),
        "--pr-tool-admission", str(paths["admission"]),
        "--external-witness", str(paths["witness"]),
        "--command-preview", str(paths["preview"]),
        "--metadata", str(paths["metadata"]),
        "--pr-readiness", str(paths["readiness"]),
        "--output", str(output_path),
        "--json",
    ])
    captured = capsys.readouterr()
    receipt = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert receipt["receipt_id"] == "developer_workflow_operator_receipt.v1"
    assert receipt["execution_performed"] is False
    assert '"SolvedUnverified"' in captured.out
