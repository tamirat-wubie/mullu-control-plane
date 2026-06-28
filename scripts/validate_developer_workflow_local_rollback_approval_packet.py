#!/usr/bin/env python3
"""Validate the Developer Workflow local rollback approval packet.

Purpose: prove rollback approval packets are schema-valid, local-only,
operator-evidence-bound, and faithful to the rollback summary packet.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: rollback approval schema, rollback summary validator, and
workspace schema validator.
Invariants:
  - The packet never claims rollback execution or external effects.
  - Non-approved states cannot authorize deletion.
  - Approved states require operator evidence and selected known artifacts.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_developer_workflow_local_rollback_summary_packet import (  # noqa: E402
    validate_developer_workflow_local_rollback_summary_packet,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "developer_workflow_local_rollback_approval_packet.schema.json"
DEFAULT_PACKET = REPO_ROOT / "examples" / "developer_workflow_local_rollback_approval_packet.foundation.json"
DEFAULT_ROLLBACK_SUMMARY = REPO_ROOT / "examples" / "developer_workflow_local_rollback_summary_packet.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_approval_packet_validation.json"


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowLocalRollbackApprovalPacketValidation:
    """Validation report for the local rollback approval packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    packet_path: str
    rollback_summary_path: str
    packet_status: str
    approval_status: str
    selected_artifact_count: int
    delete_execution_allowed: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_developer_workflow_local_rollback_approval_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = DEFAULT_PACKET,
    rollback_summary_path: Path = DEFAULT_ROLLBACK_SUMMARY,
) -> DeveloperWorkflowLocalRollbackApprovalPacketValidation:
    """Validate schema and semantic consistency for a rollback approval packet."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "rollback approval schema", errors)
    packet = _load_json_object(packet_path, "rollback approval packet", errors)
    rollback_summary = _load_json_object(rollback_summary_path, "rollback summary packet", errors)
    packet_label = _path_label(packet_path)
    if schema and packet:
        errors.extend(f"{packet_label}: {error}" for error in _validate_schema_instance(schema, packet))
    if rollback_summary and _path_label(rollback_summary_path) == _path_label(DEFAULT_ROLLBACK_SUMMARY):
        summary_validation = validate_developer_workflow_local_rollback_summary_packet(
            packet_path=rollback_summary_path,
        )
        errors.extend(f"{_path_label(rollback_summary_path)}: {error}" for error in summary_validation.errors)
    if packet and rollback_summary:
        _validate_packet_semantics(packet, rollback_summary, errors, packet_label)
    return DeveloperWorkflowLocalRollbackApprovalPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        packet_path=packet_label,
        rollback_summary_path=_path_label(rollback_summary_path),
        packet_status=str(packet.get("packet_status", "")) if isinstance(packet, Mapping) else "",
        approval_status=str(packet.get("approval_status", "")) if isinstance(packet, Mapping) else "",
        selected_artifact_count=int(packet.get("selected_artifact_count", 0) or 0)
        if isinstance(packet, Mapping)
        else 0,
        delete_execution_allowed=packet.get("delete_execution_allowed") is True
        if isinstance(packet, Mapping)
        else False,
    )


def write_developer_workflow_local_rollback_approval_packet_validation(
    validation: DeveloperWorkflowLocalRollbackApprovalPacketValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic rollback approval validation record."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_packet_semantics(
    packet: Mapping[str, Any],
    rollback_summary: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if packet.get("external_effects_allowed") is not False:
        errors.append(f"{label}: external_effects_allowed must be false")
    if packet.get("rollback_execution_performed") is not False:
        errors.append(f"{label}: rollback_execution_performed must be false")
    if packet.get("execution_boundary") != "local_lab_only":
        errors.append(f"{label}: execution_boundary must be local_lab_only")
    approval_status = str(packet.get("approval_status") or "")
    operator_approval = packet.get("operator_approval", {})
    if not isinstance(operator_approval, Mapping):
        errors.append(f"{label}: operator_approval must be an object")
        operator_approval = {}
    if operator_approval.get("approval_status") != approval_status:
        errors.append(f"{label}: operator approval_status must match packet approval_status")
    expected_packet_status = {
        "pending": "awaiting_operator_approval",
        "approved": "approval_recorded",
        "rejected": "approval_rejected",
        "deferred": "approval_deferred",
    }.get(approval_status)
    if packet.get("packet_status") != expected_packet_status:
        errors.append(f"{label}: packet_status must match approval_status")
    summary_artifacts = _artifact_map(rollback_summary)
    selected_ids = packet.get("selected_artifact_ids", ())
    if not isinstance(selected_ids, list):
        errors.append(f"{label}: selected_artifact_ids must be a list")
        selected_ids = []
    selected_id_tuple = tuple(str(item) for item in selected_ids if str(item).strip())
    if len(selected_id_tuple) != len(set(selected_id_tuple)):
        errors.append(f"{label}: selected_artifact_ids must be unique")
    selected_count = int(packet.get("selected_artifact_count", -1) or 0)
    if selected_count != len(selected_id_tuple):
        errors.append(f"{label}: selected_artifact_count must match selected_artifact_ids")
    for artifact_id in selected_id_tuple:
        if artifact_id not in summary_artifacts:
            errors.append(f"{label}: selected artifact {artifact_id} is not present in rollback summary")
    authorization_allowed = approval_status == "approved" and bool(selected_id_tuple)
    if packet.get("delete_execution_allowed") is not authorization_allowed:
        errors.append(f"{label}: delete_execution_allowed must match approval state and selection")
    if approval_status == "approved":
        _require_approval_evidence(operator_approval, errors, label)
    elif packet.get("delete_execution_allowed") is True:
        errors.append(f"{label}: non-approved rollback approval cannot allow deletion")
    expected_scope = _expected_scope(selected_id_tuple, summary_artifacts)
    if packet.get("approval_scope") != expected_scope:
        errors.append(f"{label}: approval_scope must match selected artifacts")
    authorized_artifacts = packet.get("authorized_artifacts", ())
    if not isinstance(authorized_artifacts, list):
        errors.append(f"{label}: authorized_artifacts must be a list")
        return
    if len(authorized_artifacts) != len(selected_id_tuple):
        errors.append(f"{label}: authorized_artifacts length must match selected_artifact_ids")
    observed_ids: list[str] = []
    for artifact in authorized_artifacts:
        if not isinstance(artifact, Mapping):
            errors.append(f"{label}: authorized artifact row must be an object")
            continue
        artifact_id = str(artifact.get("artifact_id") or "")
        observed_ids.append(artifact_id)
        expected = summary_artifacts.get(artifact_id)
        if expected is None:
            errors.append(f"{label}: authorized artifact {artifact_id} is not present in rollback summary")
            continue
        if artifact.get("path") != expected.get("path"):
            errors.append(f"{label}: authorized artifact {artifact_id} path must match rollback summary")
        if artifact.get("rollback_command") != expected.get("rollback_command"):
            errors.append(f"{label}: authorized artifact {artifact_id} rollback_command must match rollback summary")
        if artifact.get("approval_status") != approval_status:
            errors.append(f"{label}: authorized artifact {artifact_id} approval_status must match packet")
        if artifact.get("execution_allowed") is not authorization_allowed:
            errors.append(f"{label}: authorized artifact {artifact_id} execution_allowed must match approval state")
        if artifact.get("required_confirmation") is not True:
            errors.append(f"{label}: authorized artifact {artifact_id} required_confirmation must be true")
    if tuple(observed_ids) != selected_id_tuple:
        errors.append(f"{label}: authorized_artifacts order must match selected_artifact_ids")


def _require_approval_evidence(operator_approval: Mapping[str, Any], errors: list[str], label: str) -> None:
    for field in ("approved_by", "approved_at", "approval_evidence_ref"):
        if not str(operator_approval.get(field) or "").strip():
            errors.append(f"{label}: approved rollback approval requires {field}")


def _artifact_map(packet: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    artifacts = packet.get("artifacts", ())
    if not isinstance(artifacts, list):
        return {}
    mapped: dict[str, Mapping[str, Any]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        artifact_id = str(artifact.get("artifact_id") or "")
        if artifact_id:
            mapped[artifact_id] = artifact
    return mapped


def _expected_scope(
    selected_ids: Sequence[str],
    summary_artifacts: Mapping[str, Mapping[str, Any]],
) -> str:
    if not selected_ids:
        return "none"
    if set(selected_ids) == set(summary_artifacts):
        return "all_generated_artifacts"
    return "selected_artifacts"


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
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
    """Parse rollback approval validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Developer Workflow local rollback approval packet.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--rollback-summary", default=str(DEFAULT_ROLLBACK_SUMMARY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for rollback approval packet validation."""

    args = parse_args(argv)
    validation = validate_developer_workflow_local_rollback_approval_packet(
        schema_path=Path(args.schema),
        packet_path=Path(args.packet),
        rollback_summary_path=Path(args.rollback_summary),
    )
    write_developer_workflow_local_rollback_approval_packet_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("DEVELOPER WORKFLOW LOCAL ROLLBACK APPROVAL PACKET VALID")
    else:
        print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK APPROVAL PACKET INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
