#!/usr/bin/env python3
"""Build the end-to-end Developer Workflow PR readiness bundle.

Purpose: link receipts, approvals, candidate, admission, external witness,
command preview, metadata, and rollback into one operator-facing packet.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: local Developer Workflow packet artifacts and schema validation.
Invariants:
  - The bundle is projection-only and non-executing.
  - External execution readiness requires every upstream artifact to be ready.
  - Rollback evidence and commands are preserved when present.
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
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "pr_readiness_bundle.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_readiness_bundle.generated.json"


@dataclass(frozen=True, slots=True)
class PrReadinessBundleValidation:
    """Validation report for a PR readiness bundle."""

    ok: bool
    errors: tuple[str, ...]
    bundle_path: str
    readiness_status: str
    ready_for_external_pr_execution: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_pr_readiness_bundle(
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
) -> dict[str, Any]:
    """Return a projection-only PR readiness bundle."""

    artifacts = {
        "sandbox_receipts": _artifact(
            "sandbox_receipts",
            str(sandbox_receipts.get("bundle_status") or "awaiting_receipts"),
            sandbox_receipts.get("bundle_status") == "receipts_complete",
            sandbox_receipts,
        ),
        "approval_packet": _artifact(
            "approval_packet",
            str(approval_packet.get("approval_status") or "pending"),
            approval_packet.get("approval_status") == "approved",
            approval_packet,
        ),
        "local_candidate": _artifact(
            "local_candidate",
            str(local_candidate.get("candidate_status") or "blocked"),
            local_candidate.get("candidate_ready") is True,
            local_candidate,
        ),
        "pr_tool_admission": _artifact(
            "pr_tool_admission",
            str(pr_tool_admission.get("admission_status") or "blocked_candidate_incomplete"),
            pr_tool_admission.get("local_pr_tool_admitted") is True,
            pr_tool_admission,
        ),
        "external_approval_witness": _artifact(
            "external_approval_witness",
            str(external_witness.get("execution_status") or "awaiting_local_pr_tool_admission"),
            external_witness.get("external_effects_allowed") is True,
            external_witness,
        ),
        "command_preview": _artifact(
            "command_preview",
            str(command_preview.get("preview_status") or "blocked"),
            command_preview.get("commands_rendered") is True,
            command_preview,
        ),
        "metadata": _artifact(
            "metadata",
            str(metadata.get("metadata_status") or "blocked_candidate_incomplete"),
            metadata.get("metadata_status") == "ready_for_preview",
            metadata,
        ),
    }
    ready = all(item["ready"] for item in artifacts.values())
    readiness_status = _readiness_status(artifacts)
    bundle = {
        "bundle_id": "pr_readiness_bundle.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": _workflow_run_id(
            sandbox_receipts,
            approval_packet,
            local_candidate,
            pr_tool_admission,
            external_witness,
            command_preview,
            metadata,
        ),
        "readiness_status": readiness_status,
        "ready_for_external_pr_execution": ready,
        "preview_only": True,
        "execution_performed": False,
        "external_effects_allowed": ready,
        "pr_creation_allowed": ready,
        "branch_push_allowed": ready,
        "artifacts": artifacts,
        "next_evidence": _next_evidence(artifacts),
        "rollback": _rollback(command_preview, metadata),
        "operator_summary": _operator_summary(readiness_status),
        "source_refs": {
            "sandbox_receipt_bundle_path": _path_label(sandbox_receipts_path),
            "approval_packet_path": _path_label(approval_packet_path),
            "local_candidate_packet_path": _path_label(local_candidate_path),
            "pr_tool_admission_packet_path": _path_label(pr_tool_admission_path),
            "external_approval_witness_path": _path_label(external_witness_path),
            "command_preview_packet_path": _path_label(command_preview_path),
            "metadata_packet_path": _path_label(metadata_path),
            "bundle_builder": "python scripts/build_pr_readiness_bundle.py",
        },
        "bundle_hash": "",
    }
    bundle["bundle_hash"] = canonical_hash(bundle)
    return bundle


def validate_pr_readiness_bundle(
    *,
    bundle: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    bundle_path: Path = Path("<generated>"),
) -> PrReadinessBundleValidation:
    """Validate schema and end-to-end readiness semantics."""

    errors: list[str] = []
    schema = _load_json_object(schema_path)
    errors.extend(str(error) for error in _validate_schema_instance(schema, dict(bundle)))
    _validate_bundle_semantics(bundle, errors)
    return PrReadinessBundleValidation(
        ok=not errors,
        errors=tuple(errors),
        bundle_path=_path_label(bundle_path),
        readiness_status=str(bundle.get("readiness_status") or ""),
        ready_for_external_pr_execution=bundle.get("ready_for_external_pr_execution") is True,
    )


def write_pr_readiness_bundle(bundle: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic PR readiness bundle."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_bundle_semantics(bundle: Mapping[str, Any], errors: list[str]) -> None:
    if bundle.get("preview_only") is not True:
        errors.append("preview_only_must_be_true")
    if bundle.get("execution_performed") is not False:
        errors.append("execution_performed_must_be_false")
    artifacts = bundle.get("artifacts", {})
    if not isinstance(artifacts, Mapping):
        errors.append("artifacts_must_be_object")
        return
    ready = all(isinstance(item, Mapping) and item.get("ready") is True for item in artifacts.values())
    for field_name in ("ready_for_external_pr_execution", "external_effects_allowed", "pr_creation_allowed", "branch_push_allowed"):
        if bundle.get(field_name) is not ready:
            errors.append(f"{field_name}_mismatch")
    if bundle.get("readiness_status") != _readiness_status(artifacts):
        errors.append("readiness_status_mismatch")
    if bundle.get("bundle_hash") != canonical_hash({**dict(bundle), "bundle_hash": ""}):
        errors.append("bundle_hash_mismatch")


def _artifact(artifact_id: str, status: str, ready: bool, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"artifact_id": artifact_id, "status": status, "ready": ready, "hash": _payload_hash(payload)}


def _payload_hash(payload: Mapping[str, Any]) -> str:
    for field_name in ("packet_hash", "witness_hash", "bundle_hash"):
        value = str(payload.get(field_name) or "")
        if value:
            return value
    return canonical_hash(payload)


def _readiness_status(artifacts: Mapping[str, Any]) -> str:
    if not _ready(artifacts, "sandbox_receipts"):
        return "awaiting_sandbox_receipts"
    if not _ready(artifacts, "approval_packet") or not _ready(artifacts, "local_candidate"):
        return "awaiting_operator_approval"
    if not _ready(artifacts, "pr_tool_admission") or not _ready(artifacts, "external_approval_witness"):
        return "awaiting_external_pr_approval"
    return "ready_for_external_pr_execution" if all(_ready(artifacts, key) for key in artifacts) else "awaiting_external_pr_approval"


def _ready(artifacts: Mapping[str, Any], key: str) -> bool:
    item = artifacts.get(key, {})
    return isinstance(item, Mapping) and item.get("ready") is True


def _next_evidence(artifacts: Mapping[str, Any]) -> list[str]:
    return [str(key) for key, item in artifacts.items() if isinstance(item, Mapping) and item.get("ready") is not True]


def _rollback(command_preview: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
    commands: list[str] = []
    for item in command_preview.get("rollback_preview", ()) if isinstance(command_preview.get("rollback_preview"), list) else ():
        if isinstance(item, Mapping) and str(item.get("command") or "").strip():
            commands.append(str(item["command"]))
    rollback = metadata.get("rollback", {})
    evidence_refs = []
    if isinstance(rollback, Mapping):
        evidence_refs = [str(item) for item in rollback.get("evidence_refs", ())]
    return {"required": True, "evidence_refs": evidence_refs, "commands": commands}


def _operator_summary(readiness_status: str) -> str:
    if readiness_status == "ready_for_external_pr_execution":
        return "All readiness artifacts are linked; external PR execution still requires operator-mediated command execution."
    if readiness_status == "awaiting_sandbox_receipts":
        return "Sandbox receipt bundle is incomplete; PR execution remains blocked."
    if readiness_status == "awaiting_operator_approval":
        return "Local evidence exists but operator approval or local candidate readiness is incomplete."
    return "External PR approval, command preview, or metadata readiness is incomplete."


def _workflow_run_id(*payloads: Mapping[str, Any]) -> str:
    for payload in payloads:
        value = str(payload.get("workflow_run_id") or "").strip()
        if value:
            return value
    return "developer_workflow_v1_foundation_run"


def canonical_hash(payload: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 hash for a JSON-compatible payload."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


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
    """Parse PR readiness bundle builder arguments."""

    parser = argparse.ArgumentParser(description="Build projection-only PR readiness bundle.")
    parser.add_argument("--sandbox-receipts", default=str(DEFAULT_SANDBOX_RECEIPTS))
    parser.add_argument("--approval-packet", default=str(DEFAULT_APPROVAL_PACKET))
    parser.add_argument("--local-candidate", default=str(DEFAULT_LOCAL_CANDIDATE))
    parser.add_argument("--pr-tool-admission", default=str(DEFAULT_PR_TOOL_ADMISSION))
    parser.add_argument("--external-witness", default=str(DEFAULT_EXTERNAL_WITNESS))
    parser.add_argument("--command-preview", default=str(DEFAULT_COMMAND_PREVIEW))
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for PR readiness bundle building."""

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
        }
        payloads = {key: _load_json_object(path) for key, path in paths.items()}
        bundle = build_pr_readiness_bundle(
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
        )
        output_path = write_pr_readiness_bundle(bundle, Path(args.output))
        validation = validate_pr_readiness_bundle(
            bundle=bundle,
            schema_path=Path(args.schema),
            bundle_path=output_path,
        )
    except ValueError as exc:
        print(f"PR READINESS BUNDLE INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"PR READINESS BUNDLE INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(bundle, indent=2, sort_keys=True))
    else:
        print(f"PR READINESS BUNDLE BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
