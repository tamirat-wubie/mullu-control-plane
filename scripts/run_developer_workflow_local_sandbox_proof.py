#!/usr/bin/env python3
"""Run the local Developer Workflow v1 sandbox proof path.

Purpose: collect one or more local sandbox receipt evidence records, build the
sandbox receipt bundle, validate it, build downstream PR-readiness projection
packets, and print the opt-in control tower URL.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: local artifact files, sandbox receipt evidence collector, bundle
builder, downstream PR packet builders, and validators.
Invariants:
  - The runner does not execute arbitrary commands, write source files, open PRs,
    call connectors, or mutate external state.
  - Only explicitly named local artifact files are read.
  - Evidence, bundle, and readiness outputs are local JSON receipts.
  - Generated receipts must validate before the runner reports ok=true.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_developer_workflow_sandbox_receipt_bundle import (  # noqa: E402
    build_developer_workflow_sandbox_receipt_bundle,
    write_developer_workflow_sandbox_receipt_bundle,
)
from scripts.build_developer_workflow_sandbox_receipt_attachment_packet import (  # noqa: E402
    build_developer_workflow_sandbox_receipt_attachment_packet,
    write_developer_workflow_sandbox_receipt_attachment_packet,
)
from scripts.build_developer_workflow_local_rollback_summary_packet import (  # noqa: E402
    build_developer_workflow_local_rollback_summary_packet,
    write_developer_workflow_local_rollback_summary_packet,
)
from scripts.build_developer_workflow_local_rollback_approval_packet import (  # noqa: E402
    build_developer_workflow_local_rollback_approval_packet,
    write_developer_workflow_local_rollback_approval_packet,
)
from scripts.build_external_pr_execution_approval_witness import (  # noqa: E402
    build_external_pr_execution_approval_witness,
    validate_external_pr_execution_approval_witness,
    write_external_pr_execution_approval_witness,
)
from scripts.build_developer_workflow_operator_receipt import (  # noqa: E402
    build_developer_workflow_operator_receipt,
    validate_developer_workflow_operator_receipt,
    write_developer_workflow_operator_receipt,
)
from scripts.build_local_pr_candidate_packet import (  # noqa: E402
    build_local_pr_candidate_packet,
    validate_local_pr_candidate_packet,
    write_local_pr_candidate_packet,
)
from scripts.build_pr_command_preview_packet import (  # noqa: E402
    build_pr_command_preview_packet,
    validate_pr_command_preview_packet,
    write_pr_command_preview_packet,
)
from scripts.build_pr_metadata_packet import (  # noqa: E402
    build_pr_metadata_packet,
    validate_pr_metadata_packet,
    write_pr_metadata_packet,
)
from scripts.build_pr_preparation_approval_packet import (  # noqa: E402
    build_pr_preparation_approval_packet,
    validate_pr_preparation_approval_packet,
    write_pr_preparation_approval_packet,
)
from scripts.build_pr_readiness_bundle import (  # noqa: E402
    build_pr_readiness_bundle,
    validate_pr_readiness_bundle,
    write_pr_readiness_bundle,
)
from scripts.build_pr_tool_admission_packet import (  # noqa: E402
    build_pr_tool_admission_packet,
    validate_pr_tool_admission_packet,
    write_pr_tool_admission_packet,
)
from scripts.collect_developer_workflow_sandbox_receipt_evidence import (  # noqa: E402
    CANONICAL_RECEIPT_IDS,
    collect_developer_workflow_sandbox_receipt_evidence,
    write_developer_workflow_sandbox_receipt_evidence,
)
from scripts.validate_developer_workflow_sandbox_receipt_bundle import (  # noqa: E402
    validate_developer_workflow_sandbox_receipt_bundle,
)
from scripts.validate_developer_workflow_sandbox_receipt_attachment_packet import (  # noqa: E402
    validate_developer_workflow_sandbox_receipt_attachment_packet,
)
from scripts.validate_developer_workflow_local_rollback_summary_packet import (  # noqa: E402
    validate_developer_workflow_local_rollback_summary_packet,
)
from scripts.validate_developer_workflow_local_rollback_approval_packet import (  # noqa: E402
    validate_developer_workflow_local_rollback_approval_packet,
)


DEFAULT_EXISTING_EVIDENCE = REPO_ROOT / "examples" / "developer_workflow_sandbox_receipt_evidence.partial.json"
DEFAULT_EVIDENCE_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_sandbox_receipt_evidence.collected.json"
DEFAULT_BUNDLE_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_sandbox_receipt_bundle.collected.json"
DEFAULT_SANDBOX_TO_PR_PACKET_OUTPUT = REPO_ROOT / ".change_assurance" / "sandbox_to_pr_preparation_packet.generated.json"
DEFAULT_ATTACHMENT_PACKET_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "developer_workflow_sandbox_receipt_attachment_packet.generated.json"
)
DEFAULT_APPROVAL_PACKET_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_preparation_approval_packet.generated.json"
DEFAULT_LOCAL_CANDIDATE_OUTPUT = REPO_ROOT / ".change_assurance" / "local_pr_candidate_packet.generated.json"
DEFAULT_PR_TOOL_ADMISSION_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_tool_admission_packet.generated.json"
DEFAULT_EXTERNAL_WITNESS_OUTPUT = REPO_ROOT / ".change_assurance" / "external_pr_execution_approval_witness.generated.json"
DEFAULT_COMMAND_PREVIEW_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_command_preview_packet.generated.json"
DEFAULT_METADATA_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_metadata_packet.generated.json"
DEFAULT_PR_READINESS_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_readiness_bundle.generated.json"
DEFAULT_OPERATOR_RECEIPT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_operator_receipt.generated.json"
DEFAULT_REPORT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_local_sandbox_proof_report.generated.json"
DEFAULT_ROLLBACK_SUMMARY_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_summary_packet.generated.json"
)
DEFAULT_ROLLBACK_APPROVAL_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_approval_packet.generated.json"
)
DEFAULT_WORKFLOW_RUN_ID = "developer_workflow_v1_foundation_run"
DEFAULT_CONTROL_TOWER_PATH = "/operator/control-tower"
DEFAULT_WORKFLOW_PATH = "/operator/developer-workflow/read-model"
DEFAULT_CANDIDATE_TITLE = "Governed Developer Workflow local proof"
DEFAULT_CANDIDATE_BRANCH = "codex/developer-workflow-local-proof"
DEFAULT_CANDIDATE_SUMMARY = "Prepare local sandbox receipt evidence and PR readiness projection without external effects."


@dataclass(frozen=True, slots=True)
class LocalSandboxProofReport:
    """Proof report emitted by the local sandbox proof runner."""

    ok: bool
    errors: tuple[str, ...]
    evidence_path: str
    bundle_path: str
    attachment_packet_path: str
    attachment_packet_status: str
    next_attachment_id: str
    bundle_status: str
    completed_count: int
    required_count: int
    pr_readiness_bundle_path: str
    operator_receipt_path: str
    pr_readiness_status: str
    ready_for_external_pr_execution: bool
    command_preview_rendered: bool
    execution_performed: bool
    control_tower_url: str
    workflow_read_model_url: str
    external_effects_allowed: bool
    generated_artifacts: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def write_developer_workflow_local_sandbox_proof_report(
    report: LocalSandboxProofReport,
    output_path: Path,
) -> Path:
    """Write the local sandbox proof report for control tower readback."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def run_developer_workflow_local_sandbox_proof(
    *,
    existing_evidence_path: Path | None,
    evidence_output_path: Path,
    bundle_output_path: Path,
    workflow_run_id: str,
    receipt_id: str | None,
    before_file: Path | None,
    after_file: Path | None,
    diff_file: Path | None,
    command: str | None,
    rollback_command: str | None,
    evidence_refs: Sequence[str],
    sandbox_to_pr_packet_output_path: Path = DEFAULT_SANDBOX_TO_PR_PACKET_OUTPUT,
    attachment_packet_output_path: Path = DEFAULT_ATTACHMENT_PACKET_OUTPUT,
    receipt_manifest_path: Path | None = None,
    approval_packet_output_path: Path = DEFAULT_APPROVAL_PACKET_OUTPUT,
    local_candidate_output_path: Path = DEFAULT_LOCAL_CANDIDATE_OUTPUT,
    pr_tool_admission_output_path: Path = DEFAULT_PR_TOOL_ADMISSION_OUTPUT,
    external_witness_output_path: Path = DEFAULT_EXTERNAL_WITNESS_OUTPUT,
    command_preview_output_path: Path = DEFAULT_COMMAND_PREVIEW_OUTPUT,
    metadata_output_path: Path = DEFAULT_METADATA_OUTPUT,
    pr_readiness_output_path: Path = DEFAULT_PR_READINESS_OUTPUT,
    operator_receipt_output_path: Path = DEFAULT_OPERATOR_RECEIPT_OUTPUT,
    candidate_title: str = DEFAULT_CANDIDATE_TITLE,
    candidate_branch_name: str = DEFAULT_CANDIDATE_BRANCH,
    candidate_summary: str = DEFAULT_CANDIDATE_SUMMARY,
    target_branch: str = "main",
    pr_body_path: str = ".change_assurance/pr_body.md",
    pr_preparation_approval_status: str = "pending",
    external_pr_approval_status: str = "pending",
    control_tower_base_url: str = DEFAULT_CONTROL_TOWER_PATH,
    workflow_read_model_base_url: str = DEFAULT_WORKFLOW_PATH,
) -> LocalSandboxProofReport:
    """Collect, build, validate, and report the local sandbox-to-PR proof path."""

    try:
        existing_evidence = _load_optional_json_object(existing_evidence_path)
        if receipt_manifest_path is None:
            evidence = _collect_single_receipt_evidence(
                existing_evidence=existing_evidence,
                workflow_run_id=workflow_run_id,
                receipt_id=receipt_id,
                before_file=before_file,
                after_file=after_file,
                diff_file=diff_file,
                command=command,
                rollback_command=rollback_command,
                evidence_refs=evidence_refs,
            )
        else:
            evidence = _collect_manifest_receipt_evidence(
                existing_evidence=existing_evidence,
                workflow_run_id=workflow_run_id,
                receipt_manifest_path=receipt_manifest_path,
            )
        evidence_path = write_developer_workflow_sandbox_receipt_evidence(evidence, evidence_output_path)
        bundle = build_developer_workflow_sandbox_receipt_bundle(evidence)
        bundle_path = write_developer_workflow_sandbox_receipt_bundle(bundle, bundle_output_path)
        sandbox_validation = validate_developer_workflow_sandbox_receipt_bundle(bundle_path=bundle_path)
        sandbox_to_pr_packet = _sandbox_to_pr_packet_for_attachment_builder(bundle)
        sandbox_to_pr_packet_path = _write_json_object(sandbox_to_pr_packet, sandbox_to_pr_packet_output_path)
        attachment_packet = build_developer_workflow_sandbox_receipt_attachment_packet(
            sandbox_to_pr_packet=sandbox_to_pr_packet,
            sandbox_to_pr_packet_path=sandbox_to_pr_packet_path,
            sandbox_receipt_bundle=bundle,
            sandbox_receipt_bundle_path=bundle_path,
        )
        attachment_packet_path = write_developer_workflow_sandbox_receipt_attachment_packet(
            attachment_packet,
            attachment_packet_output_path,
        )
        attachment_validation = validate_developer_workflow_sandbox_receipt_attachment_packet(
            packet_path=attachment_packet_path,
            sandbox_to_pr_packet_path=sandbox_to_pr_packet_path,
            sandbox_receipt_bundle_path=bundle_path,
        )
        readiness = _build_pr_readiness_chain(
            sandbox_receipt_bundle=bundle,
            sandbox_receipt_bundle_path=bundle_path,
            approval_packet_output_path=approval_packet_output_path,
            local_candidate_output_path=local_candidate_output_path,
            pr_tool_admission_output_path=pr_tool_admission_output_path,
            external_witness_output_path=external_witness_output_path,
            command_preview_output_path=command_preview_output_path,
            metadata_output_path=metadata_output_path,
            pr_readiness_output_path=pr_readiness_output_path,
            operator_receipt_output_path=operator_receipt_output_path,
            candidate_title=candidate_title,
            candidate_branch_name=candidate_branch_name,
            candidate_summary=candidate_summary,
            target_branch=target_branch,
            pr_body_path=pr_body_path,
            pr_preparation_approval_status=pr_preparation_approval_status,
            external_pr_approval_status=external_pr_approval_status,
        )
    except ValueError as exc:
        return LocalSandboxProofReport(
            ok=False,
            errors=(str(exc),),
            evidence_path=_path_label(evidence_output_path),
            bundle_path=_path_label(bundle_output_path),
            attachment_packet_path=_path_label(attachment_packet_output_path),
            attachment_packet_status="unknown",
            next_attachment_id="unknown",
            bundle_status="unknown",
            completed_count=0,
            required_count=4,
            pr_readiness_bundle_path=_path_label(pr_readiness_output_path),
            operator_receipt_path=_path_label(operator_receipt_output_path),
            pr_readiness_status="unknown",
            ready_for_external_pr_execution=False,
            command_preview_rendered=False,
            execution_performed=False,
            control_tower_url=_opt_in_url(control_tower_base_url),
            workflow_read_model_url=_opt_in_url(workflow_read_model_base_url),
            external_effects_allowed=False,
            generated_artifacts={},
        )
    errors = tuple(sandbox_validation.errors) + tuple(attachment_validation.errors) + readiness["errors"]
    next_attachment = attachment_packet.get("next_attachment", {})
    if not isinstance(next_attachment, dict):
        next_attachment = {}
    return LocalSandboxProofReport(
        ok=sandbox_validation.ok and attachment_validation.ok and readiness["ok"],
        errors=errors,
        evidence_path=_path_label(evidence_path),
        bundle_path=_path_label(bundle_path),
        attachment_packet_path=_path_label(attachment_packet_path),
        attachment_packet_status=str(attachment_packet.get("packet_status") or "unknown"),
        next_attachment_id=str(next_attachment.get("receipt_id") or "unknown"),
        bundle_status=sandbox_validation.bundle_status,
        completed_count=sandbox_validation.completed_count,
        required_count=sandbox_validation.required_count,
        pr_readiness_bundle_path=readiness["pr_readiness_bundle_path"],
        operator_receipt_path=readiness["operator_receipt_path"],
        pr_readiness_status=readiness["pr_readiness_status"],
        ready_for_external_pr_execution=readiness["ready_for_external_pr_execution"],
        command_preview_rendered=readiness["command_preview_rendered"],
        execution_performed=readiness["execution_performed"],
        control_tower_url=_opt_in_url(control_tower_base_url),
        workflow_read_model_url=_opt_in_url(workflow_read_model_base_url),
        external_effects_allowed=readiness["external_effects_allowed"],
        generated_artifacts={
            "sandbox_to_pr_packet": _path_label(sandbox_to_pr_packet_path),
            "sandbox_receipt_attachment_packet": _path_label(attachment_packet_path),
            **readiness["generated_artifacts"],
        },
    )


def _sandbox_to_pr_packet_for_attachment_builder(sandbox_receipt_bundle: dict[str, Any]) -> dict[str, Any]:
    """Build the minimum sandbox-to-PR packet surface needed by attachment validation."""

    receipts = sandbox_receipt_bundle.get("receipts", ())
    if not isinstance(receipts, list):
        receipts = []
    receipt_status_by_id = {
        str(receipt.get("receipt_id") or ""): str(receipt.get("status") or "pending")
        for receipt in receipts
        if isinstance(receipt, dict)
    }
    next_evidence = []
    for receipt_id, label, action in (
        (
            "sandbox_patch_receipt",
            "Sandbox patch receipt",
            "attach before state, after state, diff, command, and rollback receipt",
        ),
        (
            "test_gate_receipt",
            "Test gate receipt",
            "attach bounded local test command receipt and observed result",
        ),
        (
            "diff_review_receipt",
            "Diff review receipt",
            "attach reviewed diff hash and reviewer evidence reference",
        ),
        (
            "terminal_receipt",
            "Terminal receipt",
            "attach final local receipt summary and no-external-effect witness",
        ),
    ):
        next_evidence.append({
            "evidence_id": receipt_id,
            "label": label,
            "status": "complete" if receipt_status_by_id.get(receipt_id) == "complete" else "pending",
            "action": action,
            "source": f"workflow_monitor.metadata.developer_workflow_run.receipt_checklist.{receipt_id}",
        })
    completed_count = sum(1 for item in next_evidence if item["status"] == "complete")
    return {
        "packet_id": "sandbox_to_pr_preparation_packet.v1",
        "status": "awaiting_operator_approval" if completed_count == 4 else "awaiting_receipts",
        "blocker": "operator_approval_missing" if completed_count == 4 else "sandbox_receipts_incomplete",
        "next_action": (
            "request operator approval for PR candidate"
            if completed_count == 4
            else "complete sandbox patch, test, diff, and terminal receipts"
        ),
        "next_evidence": next_evidence,
    }


def _write_json_object(payload: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _collect_single_receipt_evidence(
    *,
    existing_evidence: dict[str, Any],
    workflow_run_id: str,
    receipt_id: str | None,
    before_file: Path | None,
    after_file: Path | None,
    diff_file: Path | None,
    command: str | None,
    rollback_command: str | None,
    evidence_refs: Sequence[str],
) -> dict[str, Any]:
    """Collect one receipt using the legacy single-receipt CLI contract."""

    if not receipt_id:
        raise ValueError("receipt_id_required_without_receipt_manifest")
    if before_file is None:
        raise ValueError("before_file_required_without_receipt_manifest")
    if after_file is None:
        raise ValueError("after_file_required_without_receipt_manifest")
    if diff_file is None:
        raise ValueError("diff_file_required_without_receipt_manifest")
    if command is None:
        raise ValueError("command_required_without_receipt_manifest")
    if rollback_command is None:
        raise ValueError("rollback_command_required_without_receipt_manifest")
    return collect_developer_workflow_sandbox_receipt_evidence(
        existing_evidence=existing_evidence,
        workflow_run_id=workflow_run_id,
        receipt_id=receipt_id,
        before_file=before_file,
        after_file=after_file,
        diff_file=diff_file,
        command=command,
        rollback_command=rollback_command,
        evidence_refs=evidence_refs,
    )


def _collect_manifest_receipt_evidence(
    *,
    existing_evidence: dict[str, Any],
    workflow_run_id: str,
    receipt_manifest_path: Path,
) -> dict[str, Any]:
    """Collect multiple sandbox receipts from one explicit local manifest."""

    manifest = _load_receipt_manifest(receipt_manifest_path)
    manifest_workflow_run_id = str(manifest.get("workflow_run_id") or "").strip()
    effective_workflow_run_id = workflow_run_id.strip() or manifest_workflow_run_id or DEFAULT_WORKFLOW_RUN_ID
    current_evidence = dict(existing_evidence)
    receipts = manifest["receipts"]
    for raw_receipt in receipts:
        if not isinstance(raw_receipt, dict):
            raise ValueError("receipt_manifest_receipt_must_be_object")
        current_evidence = collect_developer_workflow_sandbox_receipt_evidence(
            existing_evidence=current_evidence,
            workflow_run_id=effective_workflow_run_id,
            receipt_id=_manifest_text(raw_receipt, "receipt_id"),
            before_file=_manifest_path(receipt_manifest_path, raw_receipt, "before_file"),
            after_file=_manifest_path(receipt_manifest_path, raw_receipt, "after_file"),
            diff_file=_manifest_path(receipt_manifest_path, raw_receipt, "diff_file"),
            command=_manifest_text(raw_receipt, "command"),
            rollback_command=_manifest_text(raw_receipt, "rollback_command"),
            evidence_refs=_manifest_refs(raw_receipt),
        )
    return current_evidence


def _load_receipt_manifest(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise ValueError(f"receipt_manifest_missing:{path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"receipt_manifest_json_parse_failed:{path}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("receipt_manifest_root_must_be_object")
    receipts = manifest.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        raise ValueError("receipt_manifest_receipts_must_be_non_empty_list")
    return manifest


def _manifest_path(manifest_path: Path, receipt: dict[str, Any], field_name: str) -> Path:
    raw_value = _manifest_text(receipt, field_name)
    path = Path(raw_value)
    if path.is_absolute():
        return path
    return manifest_path.parent / path


def _manifest_text(receipt: dict[str, Any], field_name: str) -> str:
    value = str(receipt.get(field_name) or "").strip()
    if not value:
        raise ValueError(f"receipt_manifest_{field_name}_required")
    return value


def _manifest_refs(receipt: dict[str, Any]) -> tuple[str, ...]:
    refs = receipt.get("evidence_refs")
    if not isinstance(refs, list):
        raise ValueError("receipt_manifest_evidence_refs_must_be_list")
    return tuple(str(item) for item in refs)


def _build_pr_readiness_chain(
    *,
    sandbox_receipt_bundle: dict[str, Any],
    sandbox_receipt_bundle_path: Path,
    approval_packet_output_path: Path,
    local_candidate_output_path: Path,
    pr_tool_admission_output_path: Path,
    external_witness_output_path: Path,
    command_preview_output_path: Path,
    metadata_output_path: Path,
    pr_readiness_output_path: Path,
    operator_receipt_output_path: Path,
    candidate_title: str,
    candidate_branch_name: str,
    candidate_summary: str,
    target_branch: str,
    pr_body_path: str,
    pr_preparation_approval_status: str,
    external_pr_approval_status: str,
) -> dict[str, Any]:
    """Build all local PR-readiness projections without external execution."""

    approval_packet = build_pr_preparation_approval_packet(
        sandbox_receipt_bundle=sandbox_receipt_bundle,
        bundle_path=sandbox_receipt_bundle_path,
        approval_status=pr_preparation_approval_status,
    )
    approval_packet_path = write_pr_preparation_approval_packet(approval_packet, approval_packet_output_path)

    local_candidate = build_local_pr_candidate_packet(
        approval_packet=approval_packet,
        approval_packet_path=approval_packet_path,
        title=candidate_title,
        branch_name=candidate_branch_name,
        summary=candidate_summary,
    )
    local_candidate_path = write_local_pr_candidate_packet(local_candidate, local_candidate_output_path)

    pr_tool_admission = build_pr_tool_admission_packet(
        candidate_packet=local_candidate,
        candidate_packet_path=local_candidate_path,
    )
    pr_tool_admission_path = write_pr_tool_admission_packet(pr_tool_admission, pr_tool_admission_output_path)

    external_witness = build_external_pr_execution_approval_witness(
        admission_packet=pr_tool_admission,
        admission_packet_path=pr_tool_admission_path,
        approval_status=external_pr_approval_status,
    )
    external_witness_path = write_external_pr_execution_approval_witness(external_witness, external_witness_output_path)

    command_preview = build_pr_command_preview_packet(
        approval_witness=external_witness,
        approval_witness_path=external_witness_path,
        pr_body_path=pr_body_path,
    )
    command_preview_path = write_pr_command_preview_packet(command_preview, command_preview_output_path)

    metadata = build_pr_metadata_packet(
        candidate_packet=local_candidate,
        candidate_packet_path=local_candidate_path,
        command_preview_packet=command_preview,
        command_preview_packet_path=command_preview_path,
        target_branch=target_branch,
    )
    metadata_path = write_pr_metadata_packet(metadata, metadata_output_path)

    pr_readiness = build_pr_readiness_bundle(
        sandbox_receipts=sandbox_receipt_bundle,
        sandbox_receipts_path=sandbox_receipt_bundle_path,
        approval_packet=approval_packet,
        approval_packet_path=approval_packet_path,
        local_candidate=local_candidate,
        local_candidate_path=local_candidate_path,
        pr_tool_admission=pr_tool_admission,
        pr_tool_admission_path=pr_tool_admission_path,
        external_witness=external_witness,
        external_witness_path=external_witness_path,
        command_preview=command_preview,
        command_preview_path=command_preview_path,
        metadata=metadata,
        metadata_path=metadata_path,
    )
    pr_readiness_path = write_pr_readiness_bundle(pr_readiness, pr_readiness_output_path)
    operator_receipt = build_developer_workflow_operator_receipt(
        sandbox_receipts=sandbox_receipt_bundle,
        sandbox_receipts_path=sandbox_receipt_bundle_path,
        approval_packet=approval_packet,
        approval_packet_path=approval_packet_path,
        local_candidate=local_candidate,
        local_candidate_path=local_candidate_path,
        pr_tool_admission=pr_tool_admission,
        pr_tool_admission_path=pr_tool_admission_path,
        external_witness=external_witness,
        external_witness_path=external_witness_path,
        command_preview=command_preview,
        command_preview_path=command_preview_path,
        metadata=metadata,
        metadata_path=metadata_path,
        pr_readiness=pr_readiness,
        pr_readiness_path=pr_readiness_path,
    )
    operator_receipt_path = write_developer_workflow_operator_receipt(operator_receipt, operator_receipt_output_path)

    validations = (
        validate_pr_preparation_approval_packet(packet=approval_packet, packet_path=approval_packet_path),
        validate_local_pr_candidate_packet(packet=local_candidate, packet_path=local_candidate_path),
        validate_pr_tool_admission_packet(packet=pr_tool_admission, packet_path=pr_tool_admission_path),
        validate_external_pr_execution_approval_witness(witness=external_witness, witness_path=external_witness_path),
        validate_pr_command_preview_packet(packet=command_preview, packet_path=command_preview_path),
        validate_pr_metadata_packet(packet=metadata, packet_path=metadata_path),
        validate_pr_readiness_bundle(bundle=pr_readiness, bundle_path=pr_readiness_path),
        validate_developer_workflow_operator_receipt(receipt=operator_receipt, receipt_path=operator_receipt_path),
    )
    errors = tuple(error for validation in validations for error in validation.errors)
    generated_artifacts = {
        "approval_packet": _path_label(approval_packet_path),
        "local_candidate": _path_label(local_candidate_path),
        "pr_tool_admission": _path_label(pr_tool_admission_path),
        "external_approval_witness": _path_label(external_witness_path),
        "command_preview": _path_label(command_preview_path),
        "metadata": _path_label(metadata_path),
        "pr_readiness_bundle": _path_label(pr_readiness_path),
        "operator_receipt": _path_label(operator_receipt_path),
    }
    return {
        "ok": all(validation.ok for validation in validations),
        "errors": errors,
        "pr_readiness_bundle_path": _path_label(pr_readiness_path),
        "operator_receipt_path": _path_label(operator_receipt_path),
        "pr_readiness_status": str(pr_readiness.get("readiness_status") or "unknown"),
        "ready_for_external_pr_execution": pr_readiness.get("ready_for_external_pr_execution") is True,
        "command_preview_rendered": command_preview.get("commands_rendered") is True,
        "execution_performed": pr_readiness.get("execution_performed") is True,
        "external_effects_allowed": pr_readiness.get("external_effects_allowed") is True,
        "generated_artifacts": generated_artifacts,
    }


def _load_optional_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"existing_evidence_json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("existing_evidence_json_root_must_be_object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _opt_in_url(base_url: str) -> str:
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}domain=software_dev&include_local_sandbox_receipts=true"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse local sandbox proof runner arguments."""

    parser = argparse.ArgumentParser(description="Run Developer Workflow local sandbox proof path.")
    parser.add_argument("--existing-evidence", default=str(DEFAULT_EXISTING_EVIDENCE))
    parser.add_argument("--evidence-output", default=str(DEFAULT_EVIDENCE_OUTPUT))
    parser.add_argument("--bundle-output", default=str(DEFAULT_BUNDLE_OUTPUT))
    parser.add_argument("--sandbox-to-pr-packet-output", default=str(DEFAULT_SANDBOX_TO_PR_PACKET_OUTPUT))
    parser.add_argument("--attachment-packet-output", default=str(DEFAULT_ATTACHMENT_PACKET_OUTPUT))
    parser.add_argument("--approval-packet-output", default=str(DEFAULT_APPROVAL_PACKET_OUTPUT))
    parser.add_argument("--local-candidate-output", default=str(DEFAULT_LOCAL_CANDIDATE_OUTPUT))
    parser.add_argument("--pr-tool-admission-output", default=str(DEFAULT_PR_TOOL_ADMISSION_OUTPUT))
    parser.add_argument("--external-witness-output", default=str(DEFAULT_EXTERNAL_WITNESS_OUTPUT))
    parser.add_argument("--command-preview-output", default=str(DEFAULT_COMMAND_PREVIEW_OUTPUT))
    parser.add_argument("--metadata-output", default=str(DEFAULT_METADATA_OUTPUT))
    parser.add_argument("--pr-readiness-output", default=str(DEFAULT_PR_READINESS_OUTPUT))
    parser.add_argument("--operator-receipt-output", default=str(DEFAULT_OPERATOR_RECEIPT_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    parser.add_argument("--rollback-summary-output", default=str(DEFAULT_ROLLBACK_SUMMARY_OUTPUT))
    parser.add_argument("--rollback-approval-output", default=str(DEFAULT_ROLLBACK_APPROVAL_OUTPUT))
    parser.add_argument("--rollback-approval-status", default="pending", choices=("pending", "approved", "rejected", "deferred"))
    parser.add_argument("--rollback-artifact-id", action="append", default=[])
    parser.add_argument("--rollback-approved-by", default="")
    parser.add_argument("--rollback-approved-at", default="")
    parser.add_argument("--rollback-approval-evidence-ref", default="")
    parser.add_argument("--rollback-approval-note", default="")
    parser.add_argument("--workflow-run-id", default=DEFAULT_WORKFLOW_RUN_ID)
    parser.add_argument("--receipt-manifest")
    parser.add_argument("--receipt-id", choices=tuple(sorted(CANONICAL_RECEIPT_IDS)))
    parser.add_argument("--before-file")
    parser.add_argument("--after-file")
    parser.add_argument("--diff-file")
    parser.add_argument("--command")
    parser.add_argument("--rollback-command")
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--candidate-title", default=DEFAULT_CANDIDATE_TITLE)
    parser.add_argument("--candidate-branch-name", default=DEFAULT_CANDIDATE_BRANCH)
    parser.add_argument("--candidate-summary", default=DEFAULT_CANDIDATE_SUMMARY)
    parser.add_argument("--target-branch", default="main")
    parser.add_argument("--pr-body-path", default=".change_assurance/pr_body.md")
    parser.add_argument("--pr-preparation-approval-status", default="pending", choices=("pending", "approved", "rejected", "deferred"))
    parser.add_argument("--external-pr-approval-status", default="pending", choices=("pending", "approved", "rejected", "deferred"))
    parser.add_argument("--control-tower-base-url", default=DEFAULT_CONTROL_TOWER_PATH)
    parser.add_argument("--workflow-read-model-base-url", default=DEFAULT_WORKFLOW_PATH)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the local sandbox proof runner."""

    args = parse_args(argv)
    report = run_developer_workflow_local_sandbox_proof(
        existing_evidence_path=Path(args.existing_evidence) if args.existing_evidence else None,
        evidence_output_path=Path(args.evidence_output),
        bundle_output_path=Path(args.bundle_output),
        sandbox_to_pr_packet_output_path=Path(args.sandbox_to_pr_packet_output),
        attachment_packet_output_path=Path(args.attachment_packet_output),
        workflow_run_id=str(args.workflow_run_id),
        receipt_id=str(args.receipt_id) if args.receipt_id else None,
        before_file=Path(args.before_file) if args.before_file else None,
        after_file=Path(args.after_file) if args.after_file else None,
        diff_file=Path(args.diff_file) if args.diff_file else None,
        command=str(args.command) if args.command else None,
        rollback_command=str(args.rollback_command) if args.rollback_command else None,
        evidence_refs=tuple(str(value) for value in args.evidence_ref),
        receipt_manifest_path=Path(args.receipt_manifest) if args.receipt_manifest else None,
        approval_packet_output_path=Path(args.approval_packet_output),
        local_candidate_output_path=Path(args.local_candidate_output),
        pr_tool_admission_output_path=Path(args.pr_tool_admission_output),
        external_witness_output_path=Path(args.external_witness_output),
        command_preview_output_path=Path(args.command_preview_output),
        metadata_output_path=Path(args.metadata_output),
        pr_readiness_output_path=Path(args.pr_readiness_output),
        operator_receipt_output_path=Path(args.operator_receipt_output),
        candidate_title=str(args.candidate_title),
        candidate_branch_name=str(args.candidate_branch_name),
        candidate_summary=str(args.candidate_summary),
        target_branch=str(args.target_branch),
        pr_body_path=str(args.pr_body_path),
        pr_preparation_approval_status=str(args.pr_preparation_approval_status),
        external_pr_approval_status=str(args.external_pr_approval_status),
        control_tower_base_url=str(args.control_tower_base_url),
        workflow_read_model_base_url=str(args.workflow_read_model_base_url),
    )
    report_path = write_developer_workflow_local_sandbox_proof_report(report, Path(args.report_output))
    rollback_summary = build_developer_workflow_local_rollback_summary_packet(
        local_sandbox_proof_report=report.as_dict(),
        local_sandbox_proof_report_path=report_path,
    )
    rollback_summary_path = write_developer_workflow_local_rollback_summary_packet(
        rollback_summary,
        Path(args.rollback_summary_output),
    )
    rollback_validation = validate_developer_workflow_local_rollback_summary_packet(
        packet_path=rollback_summary_path,
        proof_report_path=report_path,
    )
    if not rollback_validation.ok:
        print(f"LOCAL SANDBOX PROOF ROLLBACK SUMMARY INVALID errors={list(rollback_validation.errors)}")
        return 2
    rollback_approval = build_developer_workflow_local_rollback_approval_packet(
        local_rollback_summary_packet=rollback_summary,
        local_rollback_summary_packet_path=rollback_summary_path,
        approval_status=str(args.rollback_approval_status),
        selected_artifact_ids=tuple(str(value) for value in args.rollback_artifact_id),
        approved_by=str(args.rollback_approved_by),
        approved_at=str(args.rollback_approved_at),
        approval_evidence_ref=str(args.rollback_approval_evidence_ref),
        approval_note=str(args.rollback_approval_note),
    )
    rollback_approval_path = write_developer_workflow_local_rollback_approval_packet(
        rollback_approval,
        Path(args.rollback_approval_output),
    )
    rollback_approval_validation = validate_developer_workflow_local_rollback_approval_packet(
        packet_path=rollback_approval_path,
        rollback_summary_path=rollback_summary_path,
    )
    if not rollback_approval_validation.ok:
        print(f"LOCAL SANDBOX PROOF ROLLBACK APPROVAL INVALID errors={list(rollback_approval_validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    elif report.ok:
        print(
            "LOCAL SANDBOX PROOF OK "
            f"bundle={report.bundle_path} "
            f"pr_readiness={report.pr_readiness_bundle_path} "
            f"operator_receipt={report.operator_receipt_path} "
            f"status={report.pr_readiness_status} "
            f"control_tower={report.control_tower_url}"
        )
    else:
        print(f"LOCAL SANDBOX PROOF INVALID errors={list(report.errors)}")
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
