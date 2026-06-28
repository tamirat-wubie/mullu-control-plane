#!/usr/bin/env python3
"""Build a concise Developer Workflow v1 operator receipt.

Purpose: summarize sandbox receipts, local approval, local PR candidate
readiness, external PR preview handoff, rollback, and source packet hashes in
one no-execution operator receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Developer Workflow sandbox, approval, candidate, admission,
external witness, command preview, metadata, and PR readiness packet artifacts.
Invariants:
  - The receipt does not execute commands, push branches, open pull requests,
    call connectors, merge, deploy, or mutate external state.
  - Execution performed remains false.
  - External handoff readiness is summarized from validated source packets.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SANDBOX_RECEIPTS = REPO_ROOT / "examples" / "developer_workflow_sandbox_receipt_bundle.foundation.json"
DEFAULT_APPROVAL_PACKET = REPO_ROOT / "examples" / "pr_preparation_approval_packet.foundation.json"
DEFAULT_LOCAL_CANDIDATE = REPO_ROOT / "examples" / "local_pr_candidate_packet.foundation.json"
DEFAULT_PR_TOOL_ADMISSION = REPO_ROOT / "examples" / "pr_tool_admission_packet.foundation.json"
DEFAULT_EXTERNAL_WITNESS = REPO_ROOT / "examples" / "external_pr_execution_approval_witness.foundation.json"
DEFAULT_COMMAND_PREVIEW = REPO_ROOT / "examples" / "pr_command_preview_packet.foundation.json"
DEFAULT_METADATA = REPO_ROOT / "examples" / "pr_metadata_packet.foundation.json"
DEFAULT_PR_READINESS = REPO_ROOT / "examples" / "pr_readiness_bundle.foundation.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "developer_workflow_operator_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_operator_receipt.generated.json"


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowOperatorReceiptValidation:
    """Validation report for the Developer Workflow operator receipt."""

    ok: bool
    errors: tuple[str, ...]
    receipt_path: str
    readiness_status: str
    solver_outcome: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_developer_workflow_operator_receipt(
    *,
    sandbox_receipts: Mapping[str, Any],
    sandbox_receipts_path: Path,
    approval_packet: Mapping[str, Any],
    approval_packet_path: Path,
    local_candidate: Mapping[str, Any],
    local_candidate_path: Path,
    pr_tool_admission: Mapping[str, Any],
    pr_tool_admission_path: Path,
    external_witness: Mapping[str, Any],
    external_witness_path: Path,
    command_preview: Mapping[str, Any],
    command_preview_path: Path,
    metadata: Mapping[str, Any],
    metadata_path: Path,
    pr_readiness: Mapping[str, Any],
    pr_readiness_path: Path,
) -> dict[str, Any]:
    """Return a concise no-execution operator receipt."""

    readiness_status = str(pr_readiness.get("readiness_status") or "awaiting_sandbox_receipts")
    receipt = {
        "receipt_id": "developer_workflow_operator_receipt.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": _workflow_run_id(sandbox_receipts, approval_packet, pr_readiness),
        "solver_outcome": "SolvedUnverified" if readiness_status == "ready_for_external_pr_execution" else "AwaitingEvidence",
        "execution_boundary": "local_lab_to_external_pr_preview",
        "execution_performed": False,
        "readiness_status": readiness_status,
        "sandbox_receipts": {
            "bundle_status": str(sandbox_receipts.get("bundle_status") or "unknown"),
            "completed_count": int(sandbox_receipts.get("completed_count", 0) or 0),
            "required_count": int(sandbox_receipts.get("required_count", 4) or 4),
            "bundle_hash": _payload_hash(sandbox_receipts),
        },
        "approvals": {
            "pr_preparation": {
                "status": str(approval_packet.get("approval_status") or "pending"),
                "ready": approval_packet.get("approval_status") == "approved",
            },
            "external_pr_execution": {
                "status": str(external_witness.get("approval_status") or "pending"),
                "ready": external_witness.get("external_effects_allowed") is True,
            },
        },
        "local_pr_candidate": {
            "candidate_status": str(local_candidate.get("candidate_status") or "blocked"),
            "candidate_ready": local_candidate.get("candidate_ready") is True,
            "pr_tool_admitted": pr_tool_admission.get("local_pr_tool_admitted") is True,
        },
        "external_handoff": {
            "ready_for_external_pr_execution": pr_readiness.get("ready_for_external_pr_execution") is True,
            "command_preview_rendered": command_preview.get("commands_rendered") is True,
            "external_effects_allowed": pr_readiness.get("external_effects_allowed") is True,
            "pr_creation_allowed": pr_readiness.get("pr_creation_allowed") is True,
            "branch_push_allowed": pr_readiness.get("branch_push_allowed") is True,
        },
        "next_evidence": [str(item) for item in pr_readiness.get("next_evidence", ())],
        "rollback": _rollback(pr_readiness),
        "source_refs": {
            "sandbox_receipt_bundle_path": _path_label(sandbox_receipts_path),
            "approval_packet_path": _path_label(approval_packet_path),
            "local_candidate_packet_path": _path_label(local_candidate_path),
            "pr_tool_admission_packet_path": _path_label(pr_tool_admission_path),
            "external_approval_witness_path": _path_label(external_witness_path),
            "command_preview_packet_path": _path_label(command_preview_path),
            "metadata_packet_path": _path_label(metadata_path),
            "pr_readiness_bundle_path": _path_label(pr_readiness_path),
            "receipt_builder": "python scripts/build_developer_workflow_operator_receipt.py",
        },
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt


def validate_developer_workflow_operator_receipt(
    *,
    receipt: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_path: Path = Path("<generated>"),
) -> DeveloperWorkflowOperatorReceiptValidation:
    """Validate schema and no-execution receipt semantics."""

    errors: list[str] = []
    schema = _load_json_object(schema_path)
    errors.extend(str(error) for error in _validate_schema_instance(schema, dict(receipt)))
    _validate_receipt_semantics(receipt, errors)
    return DeveloperWorkflowOperatorReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        receipt_path=_path_label(receipt_path),
        readiness_status=str(receipt.get("readiness_status") or ""),
        solver_outcome=str(receipt.get("solver_outcome") or ""),
    )


def write_developer_workflow_operator_receipt(receipt: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic operator receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_receipt_semantics(receipt: Mapping[str, Any], errors: list[str]) -> None:
    if receipt.get("execution_performed") is not False:
        errors.append("execution_performed_must_be_false")
    readiness_status = str(receipt.get("readiness_status") or "")
    expected_outcome = "SolvedUnverified" if readiness_status == "ready_for_external_pr_execution" else "AwaitingEvidence"
    if receipt.get("solver_outcome") != expected_outcome:
        errors.append("solver_outcome_mismatch")
    handoff = receipt.get("external_handoff", {})
    if not isinstance(handoff, Mapping):
        errors.append("external_handoff_must_be_object")
    else:
        ready = readiness_status == "ready_for_external_pr_execution"
        for field_name in ("ready_for_external_pr_execution", "command_preview_rendered"):
            if handoff.get(field_name) is not ready:
                errors.append(f"{field_name}_mismatch")
    if receipt.get("receipt_hash") != canonical_hash({**dict(receipt), "receipt_hash": ""}):
        errors.append("receipt_hash_mismatch")


def _rollback(pr_readiness: Mapping[str, Any]) -> dict[str, Any]:
    rollback = pr_readiness.get("rollback", {})
    if not isinstance(rollback, Mapping):
        rollback = {}
    return {
        "required": True,
        "evidence_refs": [str(item) for item in rollback.get("evidence_refs", ())],
        "commands": [str(item) for item in rollback.get("commands", ())],
    }


def canonical_hash(payload: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 hash for a JSON-compatible payload."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    for field_name in ("packet_hash", "witness_hash", "bundle_hash"):
        value = str(payload.get(field_name) or "")
        if value:
            return value
    return canonical_hash(payload)


def _workflow_run_id(*payloads: Mapping[str, Any]) -> str:
    for payload in payloads:
        value = str(payload.get("workflow_run_id") or "").strip()
        if value:
            return value
    return "developer_workflow_v1_foundation_run"


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("json_root_must_be_object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse Developer Workflow operator receipt builder arguments."""

    parser = argparse.ArgumentParser(description="Build Developer Workflow operator receipt.")
    parser.add_argument("--sandbox-receipts", default=str(DEFAULT_SANDBOX_RECEIPTS))
    parser.add_argument("--approval-packet", default=str(DEFAULT_APPROVAL_PACKET))
    parser.add_argument("--local-candidate", default=str(DEFAULT_LOCAL_CANDIDATE))
    parser.add_argument("--pr-tool-admission", default=str(DEFAULT_PR_TOOL_ADMISSION))
    parser.add_argument("--external-witness", default=str(DEFAULT_EXTERNAL_WITNESS))
    parser.add_argument("--command-preview", default=str(DEFAULT_COMMAND_PREVIEW))
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA))
    parser.add_argument("--pr-readiness", default=str(DEFAULT_PR_READINESS))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Developer Workflow operator receipt building."""

    args = parse_args(argv)
    try:
        paths = {
            "sandbox_receipts": Path(args.sandbox_receipts),
            "approval_packet": Path(args.approval_packet),
            "local_candidate": Path(args.local_candidate),
            "pr_tool_admission": Path(args.pr_tool_admission),
            "external_witness": Path(args.external_witness),
            "command_preview": Path(args.command_preview),
            "metadata": Path(args.metadata),
            "pr_readiness": Path(args.pr_readiness),
        }
        payloads = {key: _load_json_object(path) for key, path in paths.items()}
        receipt = build_developer_workflow_operator_receipt(
            sandbox_receipts=payloads["sandbox_receipts"],
            sandbox_receipts_path=paths["sandbox_receipts"],
            approval_packet=payloads["approval_packet"],
            approval_packet_path=paths["approval_packet"],
            local_candidate=payloads["local_candidate"],
            local_candidate_path=paths["local_candidate"],
            pr_tool_admission=payloads["pr_tool_admission"],
            pr_tool_admission_path=paths["pr_tool_admission"],
            external_witness=payloads["external_witness"],
            external_witness_path=paths["external_witness"],
            command_preview=payloads["command_preview"],
            command_preview_path=paths["command_preview"],
            metadata=payloads["metadata"],
            metadata_path=paths["metadata"],
            pr_readiness=payloads["pr_readiness"],
            pr_readiness_path=paths["pr_readiness"],
        )
        output_path = write_developer_workflow_operator_receipt(receipt, Path(args.output))
        validation = validate_developer_workflow_operator_receipt(
            receipt=receipt,
            schema_path=Path(args.schema),
            receipt_path=output_path,
        )
    except ValueError as exc:
        print(f"DEVELOPER WORKFLOW OPERATOR RECEIPT INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"DEVELOPER WORKFLOW OPERATOR RECEIPT INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(f"DEVELOPER WORKFLOW OPERATOR RECEIPT BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
