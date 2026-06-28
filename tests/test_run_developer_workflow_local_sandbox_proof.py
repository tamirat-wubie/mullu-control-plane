"""Tests for the Developer Workflow local sandbox proof runner.

Purpose: prove the one-command local proof path collects evidence, builds a
receipt bundle, validates it, and reports opt-in dashboard URLs.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.run_developer_workflow_local_sandbox_proof and sandbox
receipt bundle plus PR readiness validation.
Invariants: the runner does not execute commands, call connectors, open PRs,
or grant write authority; it only writes local JSON receipts.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_developer_workflow_local_sandbox_proof import (
    main,
    run_developer_workflow_local_sandbox_proof,
)
from scripts.validate_developer_workflow_sandbox_receipt_bundle import (
    validate_developer_workflow_sandbox_receipt_bundle,
)
from scripts.validate_developer_workflow_sandbox_receipt_attachment_packet import (
    validate_developer_workflow_sandbox_receipt_attachment_packet,
)
from scripts.validate_pr_readiness_bundle import validate_pr_readiness_bundle


def _artifact(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _readiness_outputs(tmp_path: Path) -> dict[str, Path]:
    return {
        "sandbox_to_pr_packet_output_path": tmp_path / "sandbox-to-pr-packet.json",
        "attachment_packet_output_path": tmp_path / "attachment-packet.json",
        "approval_packet_output_path": tmp_path / "approval-packet.json",
        "local_candidate_output_path": tmp_path / "local-candidate.json",
        "pr_tool_admission_output_path": tmp_path / "pr-tool-admission.json",
        "external_witness_output_path": tmp_path / "external-witness.json",
        "command_preview_output_path": tmp_path / "command-preview.json",
        "metadata_output_path": tmp_path / "metadata.json",
        "pr_readiness_output_path": tmp_path / "pr-readiness.json",
        "operator_receipt_output_path": tmp_path / "operator-receipt.json",
    }


def _write_complete_receipt_manifest(tmp_path: Path) -> Path:
    receipts = []
    for receipt_id in (
        "sandbox_patch_receipt",
        "test_gate_receipt",
        "diff_review_receipt",
        "terminal_receipt",
    ):
        before = _artifact(tmp_path / f"{receipt_id}.before.txt", f"{receipt_id}:before")
        after = _artifact(tmp_path / f"{receipt_id}.after.txt", f"{receipt_id}:after")
        diff = _artifact(tmp_path / f"{receipt_id}.diff.patch", f"{receipt_id}:diff")
        receipts.append(
            {
                "receipt_id": receipt_id,
                "before_file": before.name,
                "after_file": after.name,
                "diff_file": diff.name,
                "command": f"local proof command for {receipt_id}",
                "rollback_command": f"local rollback command for {receipt_id}",
                "evidence_refs": [f"proof://developer-workflow-v1/local-proof/{receipt_id}"],
            }
        )
    manifest = tmp_path / "receipt-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "workflow_run_id": "developer_workflow_v1_manifest_runner_run",
                "receipts": receipts,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def test_local_sandbox_proof_runner_collects_builds_validates_and_reports_urls(tmp_path: Path) -> None:
    before = _artifact(tmp_path / "before.txt", "before")
    after = _artifact(tmp_path / "after.txt", "after")
    diff = _artifact(tmp_path / "diff.patch", "diff")
    evidence_output = tmp_path / "evidence.json"
    bundle_output = tmp_path / "bundle.json"
    readiness_outputs = _readiness_outputs(tmp_path)

    report = run_developer_workflow_local_sandbox_proof(
        existing_evidence_path=None,
        evidence_output_path=evidence_output,
        bundle_output_path=bundle_output,
        **readiness_outputs,
        workflow_run_id="developer_workflow_v1_runner_run",
        receipt_id="sandbox_patch_receipt",
        before_file=before,
        after_file=after,
        diff_file=diff,
        command="apply_patch",
        rollback_command="git apply -R .change_assurance/sandbox_patch.diff",
        evidence_refs=("proof://developer-workflow-v1/local-proof/sandbox-patch",),
    )
    validation = validate_developer_workflow_sandbox_receipt_bundle(bundle_path=bundle_output)
    attachment_validation = validate_developer_workflow_sandbox_receipt_attachment_packet(
        packet_path=readiness_outputs["attachment_packet_output_path"],
        sandbox_to_pr_packet_path=readiness_outputs["sandbox_to_pr_packet_output_path"],
        sandbox_receipt_bundle_path=bundle_output,
    )
    readiness_validation = validate_pr_readiness_bundle(bundle_path=readiness_outputs["pr_readiness_output_path"])
    evidence = json.loads(evidence_output.read_text(encoding="utf-8"))

    assert report.ok is True
    assert validation.ok is True
    assert attachment_validation.ok is True
    assert readiness_validation.ok is True
    assert evidence_output.exists()
    assert bundle_output.exists()
    assert readiness_outputs["pr_readiness_output_path"].exists()
    assert readiness_outputs["operator_receipt_output_path"].exists()
    assert readiness_outputs["sandbox_to_pr_packet_output_path"].exists()
    assert readiness_outputs["attachment_packet_output_path"].exists()
    assert report.attachment_packet_path == str(readiness_outputs["attachment_packet_output_path"].resolve())
    assert report.attachment_packet_status == "awaiting_attachments"
    assert report.next_attachment_id == "test_gate_receipt"
    assert report.bundle_status == "awaiting_receipts"
    assert report.pr_readiness_status == "awaiting_sandbox_receipts"
    assert report.ready_for_external_pr_execution is False
    assert report.command_preview_rendered is False
    assert report.execution_performed is False
    assert report.completed_count == 1
    assert report.required_count == 4
    assert report.external_effects_allowed is False
    assert report.errors == ()
    assert report.generated_artifacts["pr_readiness_bundle"] == str(readiness_outputs["pr_readiness_output_path"].resolve())
    assert report.generated_artifacts["operator_receipt"] == str(readiness_outputs["operator_receipt_output_path"].resolve())
    assert report.generated_artifacts["sandbox_to_pr_packet"] == str(
        readiness_outputs["sandbox_to_pr_packet_output_path"].resolve()
    )
    assert report.generated_artifacts["sandbox_receipt_attachment_packet"] == str(
        readiness_outputs["attachment_packet_output_path"].resolve()
    )
    assert report.control_tower_url == "/operator/control-tower?domain=software_dev&include_local_sandbox_receipts=true"
    assert report.workflow_read_model_url == (
        "/operator/developer-workflow/read-model?domain=software_dev&include_local_sandbox_receipts=true"
    )
    assert sorted(evidence["receipts"]) == ["sandbox_patch_receipt"]


def test_local_sandbox_proof_runner_collects_complete_manifest_and_advances_to_approval(tmp_path: Path) -> None:
    evidence_output = tmp_path / "evidence.json"
    bundle_output = tmp_path / "bundle.json"
    readiness_outputs = _readiness_outputs(tmp_path)
    manifest = _write_complete_receipt_manifest(tmp_path)

    report = run_developer_workflow_local_sandbox_proof(
        existing_evidence_path=None,
        evidence_output_path=evidence_output,
        bundle_output_path=bundle_output,
        **readiness_outputs,
        workflow_run_id="",
        receipt_manifest_path=manifest,
        receipt_id=None,
        before_file=None,
        after_file=None,
        diff_file=None,
        command=None,
        rollback_command=None,
        evidence_refs=(),
    )
    evidence = json.loads(evidence_output.read_text(encoding="utf-8"))

    assert report.ok is True
    assert report.bundle_status == "receipts_complete"
    assert report.pr_readiness_status == "awaiting_operator_approval"
    assert report.ready_for_external_pr_execution is False
    assert report.command_preview_rendered is False
    assert report.execution_performed is False
    assert report.completed_count == 4
    assert report.required_count == 4
    assert report.attachment_packet_status == "attachments_complete"
    assert report.next_attachment_id == "none"
    assert report.external_effects_allowed is False
    assert report.errors == ()
    assert sorted(evidence["receipts"]) == [
        "diff_review_receipt",
        "sandbox_patch_receipt",
        "terminal_receipt",
        "test_gate_receipt",
    ]


def test_local_sandbox_proof_runner_records_local_approval_and_admits_pr_tool(tmp_path: Path) -> None:
    evidence_output = tmp_path / "evidence.json"
    bundle_output = tmp_path / "bundle.json"
    readiness_outputs = _readiness_outputs(tmp_path)

    report = run_developer_workflow_local_sandbox_proof(
        existing_evidence_path=None,
        evidence_output_path=evidence_output,
        bundle_output_path=bundle_output,
        **readiness_outputs,
        workflow_run_id="",
        receipt_manifest_path=_write_complete_receipt_manifest(tmp_path),
        receipt_id=None,
        before_file=None,
        after_file=None,
        diff_file=None,
        command=None,
        rollback_command=None,
        evidence_refs=(),
        pr_preparation_approval_status="approved",
    )
    approval_packet = json.loads(readiness_outputs["approval_packet_output_path"].read_text(encoding="utf-8"))
    local_candidate = json.loads(readiness_outputs["local_candidate_output_path"].read_text(encoding="utf-8"))
    pr_tool_admission = json.loads(readiness_outputs["pr_tool_admission_output_path"].read_text(encoding="utf-8"))

    assert report.ok is True
    assert report.bundle_status == "receipts_complete"
    assert report.pr_readiness_status == "awaiting_external_pr_approval"
    assert report.ready_for_external_pr_execution is False
    assert report.command_preview_rendered is False
    assert report.execution_performed is False
    assert report.external_effects_allowed is False
    assert approval_packet["packet_status"] == "approval_recorded"
    assert approval_packet["approval_status"] == "approved"
    assert local_candidate["candidate_status"] == "ready_for_pr_tool"
    assert local_candidate["candidate_ready"] is True
    assert pr_tool_admission["admission_status"] == "local_tool_admitted"
    assert pr_tool_admission["local_pr_tool_admitted"] is True
    assert pr_tool_admission["external_effects_allowed"] is False


def test_local_sandbox_proof_runner_renders_external_pr_commands_without_execution(tmp_path: Path) -> None:
    evidence_output = tmp_path / "evidence.json"
    bundle_output = tmp_path / "bundle.json"
    readiness_outputs = _readiness_outputs(tmp_path)

    report = run_developer_workflow_local_sandbox_proof(
        existing_evidence_path=None,
        evidence_output_path=evidence_output,
        bundle_output_path=bundle_output,
        **readiness_outputs,
        workflow_run_id="",
        receipt_manifest_path=_write_complete_receipt_manifest(tmp_path),
        receipt_id=None,
        before_file=None,
        after_file=None,
        diff_file=None,
        command=None,
        rollback_command=None,
        evidence_refs=(),
        pr_preparation_approval_status="approved",
        external_pr_approval_status="approved",
    )
    command_preview = json.loads(readiness_outputs["command_preview_output_path"].read_text(encoding="utf-8"))
    readiness_bundle = json.loads(readiness_outputs["pr_readiness_output_path"].read_text(encoding="utf-8"))
    operator_receipt = json.loads(readiness_outputs["operator_receipt_output_path"].read_text(encoding="utf-8"))

    assert report.ok is True
    assert report.pr_readiness_status == "ready_for_external_pr_execution"
    assert report.ready_for_external_pr_execution is True
    assert report.command_preview_rendered is True
    assert report.execution_performed is False
    assert command_preview["preview_status"] == "commands_rendered"
    assert command_preview["commands_rendered"] is True
    assert command_preview["execution_performed"] is False
    assert [item["effect"] for item in command_preview["command_preview"]] == [
        "push_branch",
        "open_external_pr",
    ]
    assert readiness_bundle["ready_for_external_pr_execution"] is True
    assert readiness_bundle["execution_performed"] is False
    assert operator_receipt["receipt_id"] == "developer_workflow_operator_receipt.v1"
    assert operator_receipt["solver_outcome"] == "SolvedUnverified"
    assert operator_receipt["execution_performed"] is False
    assert operator_receipt["external_handoff"]["command_preview_rendered"] is True


def test_local_sandbox_proof_runner_preserves_existing_evidence_and_advances_count(tmp_path: Path) -> None:
    before = _artifact(tmp_path / "before.txt", "before-test")
    after = _artifact(tmp_path / "after.txt", "after-test")
    diff = _artifact(tmp_path / "diff.patch", "diff-test")
    existing_evidence = tmp_path / "existing.json"
    existing_evidence.write_text(
        json.dumps(
            {
                "workflow_run_id": "developer_workflow_v1_existing_runner_run",
                "receipts": {
                    "sandbox_patch_receipt": {
                        "after_state_hash": "sha256:after",
                        "before_state_hash": "sha256:before",
                        "command": "apply_patch",
                        "diff_hash": "sha256:diff",
                        "evidence_refs": ["proof://sandbox-patch"],
                        "rollback_command": "rollback patch",
                    }
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    report = run_developer_workflow_local_sandbox_proof(
        existing_evidence_path=existing_evidence,
        evidence_output_path=tmp_path / "evidence.json",
        bundle_output_path=tmp_path / "bundle.json",
        **_readiness_outputs(tmp_path),
        workflow_run_id="",
        receipt_id="test_gate_receipt",
        before_file=before,
        after_file=after,
        diff_file=diff,
        command="python -m pytest tests/test_example.py -q",
        rollback_command="no state rollback required for read-only test command",
        evidence_refs=("proof://developer-workflow-v1/local-proof/test-gate",),
    )

    assert report.ok is True
    assert report.bundle_status == "awaiting_receipts"
    assert report.pr_readiness_status == "awaiting_sandbox_receipts"
    assert report.ready_for_external_pr_execution is False
    assert report.command_preview_rendered is False
    assert report.execution_performed is False
    assert report.completed_count == 2
    assert report.required_count == 4
    assert report.attachment_packet_status == "awaiting_attachments"
    assert report.next_attachment_id == "diff_review_receipt"
    assert report.errors == ()
    assert report.external_effects_allowed is False


def test_local_sandbox_proof_runner_reports_missing_artifact(tmp_path: Path) -> None:
    after = _artifact(tmp_path / "after.txt", "after")
    diff = _artifact(tmp_path / "diff.patch", "diff")

    report = run_developer_workflow_local_sandbox_proof(
        existing_evidence_path=None,
        evidence_output_path=tmp_path / "evidence.json",
        bundle_output_path=tmp_path / "bundle.json",
        **_readiness_outputs(tmp_path),
        workflow_run_id="developer_workflow_v1_missing_runner_run",
        receipt_id="sandbox_patch_receipt",
        before_file=tmp_path / "missing-before.txt",
        after_file=after,
        diff_file=diff,
        command="apply_patch",
        rollback_command="rollback",
        evidence_refs=("proof://missing",),
    )

    assert report.ok is False
    assert report.bundle_status == "unknown"
    assert report.attachment_packet_status == "unknown"
    assert report.next_attachment_id == "unknown"
    assert report.pr_readiness_status == "unknown"
    assert report.ready_for_external_pr_execution is False
    assert report.command_preview_rendered is False
    assert report.execution_performed is False
    assert report.completed_count == 0
    assert report.external_effects_allowed is False
    assert "artifact_file_missing" in report.errors[0]


def test_local_sandbox_proof_runner_cli_prints_json(tmp_path: Path, capsys) -> None:
    before = _artifact(tmp_path / "before.txt", "cli-before")
    after = _artifact(tmp_path / "after.txt", "cli-after")
    diff = _artifact(tmp_path / "diff.patch", "cli-diff")
    evidence_output = tmp_path / "evidence.json"
    bundle_output = tmp_path / "bundle.json"
    readiness_outputs = _readiness_outputs(tmp_path)

    exit_code = main([
        "--existing-evidence",
        "",
        "--evidence-output",
        str(evidence_output),
        "--bundle-output",
        str(bundle_output),
        "--sandbox-to-pr-packet-output",
        str(readiness_outputs["sandbox_to_pr_packet_output_path"]),
        "--attachment-packet-output",
        str(readiness_outputs["attachment_packet_output_path"]),
        "--approval-packet-output",
        str(readiness_outputs["approval_packet_output_path"]),
        "--local-candidate-output",
        str(readiness_outputs["local_candidate_output_path"]),
        "--pr-tool-admission-output",
        str(readiness_outputs["pr_tool_admission_output_path"]),
        "--external-witness-output",
        str(readiness_outputs["external_witness_output_path"]),
        "--command-preview-output",
        str(readiness_outputs["command_preview_output_path"]),
        "--metadata-output",
        str(readiness_outputs["metadata_output_path"]),
        "--pr-readiness-output",
        str(readiness_outputs["pr_readiness_output_path"]),
        "--operator-receipt-output",
        str(readiness_outputs["operator_receipt_output_path"]),
        "--report-output",
        str(tmp_path / "local-sandbox-proof-report.json"),
        "--rollback-summary-output",
        str(tmp_path / "rollback-summary.json"),
        "--rollback-approval-output",
        str(tmp_path / "rollback-approval.json"),
        "--receipt-manifest",
        str(_write_complete_receipt_manifest(tmp_path)),
        "--workflow-run-id",
        "developer_workflow_v1_cli_runner_run",
        "--json",
    ])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["completed_count"] == 4
    assert payload["attachment_packet_status"] == "attachments_complete"
    assert payload["next_attachment_id"] == "none"
    assert payload["bundle_path"] == str(bundle_output.resolve())
    assert payload["attachment_packet_path"] == str(readiness_outputs["attachment_packet_output_path"].resolve())
    assert payload["pr_readiness_bundle_path"] == str(readiness_outputs["pr_readiness_output_path"].resolve())
    assert payload["operator_receipt_path"] == str(readiness_outputs["operator_receipt_output_path"].resolve())
    assert payload["pr_readiness_status"] == "awaiting_operator_approval"
    assert payload["ready_for_external_pr_execution"] is False
    assert payload["command_preview_rendered"] is False
    assert payload["execution_performed"] is False
    assert payload["control_tower_url"].endswith("include_local_sandbox_receipts=true")
    assert evidence_output.exists()
    assert bundle_output.exists()
    assert readiness_outputs["sandbox_to_pr_packet_output_path"].exists()
    assert readiness_outputs["attachment_packet_output_path"].exists()
    assert readiness_outputs["pr_readiness_output_path"].exists()
    assert readiness_outputs["operator_receipt_output_path"].exists()
    assert (tmp_path / "local-sandbox-proof-report.json").exists()
    assert (tmp_path / "rollback-summary.json").exists()
    assert (tmp_path / "rollback-approval.json").exists()
