#!/usr/bin/env python3
"""Validate the Developer Workflow local rollback summary packet.

Purpose: prove rollback summaries are schema-valid, projection-only, and
faithful to the local sandbox proof report generated artifact set.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: rollback summary schema, local sandbox proof report validator,
and workspace schema validator.
Invariants:
  - The packet never claims rollback execution or external effects.
  - Artifact rows must match the proof report generated artifact map.
  - Rollback commands are previews and require explicit confirmation.
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

from scripts.validate_developer_workflow_local_sandbox_proof_report import (  # noqa: E402
    validate_developer_workflow_local_sandbox_proof_report,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "developer_workflow_local_rollback_summary_packet.schema.json"
DEFAULT_PACKET = REPO_ROOT / "examples" / "developer_workflow_local_rollback_summary_packet.foundation.json"
DEFAULT_PROOF_REPORT = REPO_ROOT / "examples" / "developer_workflow_local_sandbox_proof_report.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_summary_packet_validation.json"


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowLocalRollbackSummaryPacketValidation:
    """Validation report for the local rollback summary packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    packet_path: str
    proof_report_path: str
    packet_status: str
    generated_artifact_count: int
    rollback_execution_performed: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_developer_workflow_local_rollback_summary_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = DEFAULT_PACKET,
    proof_report_path: Path = DEFAULT_PROOF_REPORT,
) -> DeveloperWorkflowLocalRollbackSummaryPacketValidation:
    """Validate schema and semantic consistency for a rollback summary packet."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "rollback summary schema", errors)
    packet = _load_json_object(packet_path, "rollback summary packet", errors)
    proof_report = _load_json_object(proof_report_path, "local sandbox proof report", errors)
    packet_label = _path_label(packet_path)
    if schema and packet:
        errors.extend(f"{packet_label}: {error}" for error in _validate_schema_instance(schema, packet))
    if proof_report:
        proof_validation = validate_developer_workflow_local_sandbox_proof_report(report_path=proof_report_path)
        errors.extend(f"{_path_label(proof_report_path)}: {error}" for error in proof_validation.errors)
    if packet and proof_report:
        _validate_packet_semantics(packet, proof_report, errors, packet_label)
    return DeveloperWorkflowLocalRollbackSummaryPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        packet_path=packet_label,
        proof_report_path=_path_label(proof_report_path),
        packet_status=str(packet.get("packet_status", "")) if isinstance(packet, Mapping) else "",
        generated_artifact_count=int(packet.get("generated_artifact_count", 0) or 0) if isinstance(packet, Mapping) else 0,
        rollback_execution_performed=packet.get("rollback_execution_performed") is True
        if isinstance(packet, Mapping)
        else False,
    )


def write_developer_workflow_local_rollback_summary_packet_validation(
    validation: DeveloperWorkflowLocalRollbackSummaryPacketValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic rollback summary validation record."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_packet_semantics(
    packet: Mapping[str, Any],
    proof_report: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if packet.get("external_effects_allowed") is not False:
        errors.append(f"{label}: external_effects_allowed must be false")
    if packet.get("rollback_execution_performed") is not False:
        errors.append(f"{label}: rollback_execution_performed must be false")
    if packet.get("execution_boundary") != "local_lab_only":
        errors.append(f"{label}: execution_boundary must be local_lab_only")
    artifacts = packet.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append(f"{label}: artifacts must be a list")
        return
    proof_artifacts = proof_report.get("generated_artifacts")
    if not isinstance(proof_artifacts, Mapping):
        proof_artifacts = {}
    expected_artifacts = {
        str(artifact_id): str(path)
        for artifact_id, path in sorted(proof_artifacts.items())
        if str(artifact_id).strip() and str(path).strip()
    }
    expected_count = len(expected_artifacts)
    if int(packet.get("generated_artifact_count", -1) or 0) != expected_count:
        errors.append(f"{label}: generated_artifact_count must match proof report")
    if len(artifacts) != expected_count:
        errors.append(f"{label}: artifacts length must match proof report")
    expected_status = "rollback_ready" if expected_count else "rollback_unavailable"
    if packet.get("packet_status") != expected_status:
        errors.append(f"{label}: packet_status must match artifact availability")
    command_preview = packet.get("rollback_command_preview")
    if not isinstance(command_preview, list):
        errors.append(f"{label}: rollback_command_preview must be a list")
        command_preview = []
    observed: dict[str, str] = {}
    expected_commands: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            errors.append(f"{label}: artifact row must be an object")
            continue
        artifact_id = str(artifact.get("artifact_id") or "")
        path = str(artifact.get("path") or "")
        observed[artifact_id] = path
        expected_path = expected_artifacts.get(artifact_id)
        if expected_path is None:
            errors.append(f"{label}: artifact {artifact_id} is not present in proof report")
        elif path != expected_path:
            errors.append(f"{label}: artifact {artifact_id} path must match proof report")
        if _looks_external(path):
            errors.append(f"{label}: artifact {artifact_id} path must be workspace-local")
        if artifact.get("required_confirmation") is not True:
            errors.append(f"{label}: artifact {artifact_id} required_confirmation must be true")
        if artifact.get("artifact_status") != "reported":
            errors.append(f"{label}: artifact {artifact_id} artifact_status must be reported")
        if artifact.get("rollback_action") != "delete_generated_artifact":
            errors.append(f"{label}: artifact {artifact_id} rollback_action must be delete_generated_artifact")
        expected_command = f"Remove-Item -LiteralPath {_powershell_single_quoted(path)} -Force"
        expected_commands.append(expected_command)
        if artifact.get("rollback_command") != expected_command:
            errors.append(f"{label}: artifact {artifact_id} rollback_command must match path preview")
        if _looks_external(str(artifact.get("rollback_command") or "")):
            errors.append(f"{label}: artifact {artifact_id} rollback_command must not target external endpoints")
    if observed != expected_artifacts:
        errors.append(f"{label}: artifact ids must match proof report generated_artifacts")
    if [str(item) for item in command_preview] != expected_commands:
        errors.append(f"{label}: rollback_command_preview must match artifact rollback commands")


def _powershell_single_quoted(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _looks_external(value: str) -> bool:
    lowered = value.lower().strip()
    return lowered.startswith(("http://", "https://", "app://"))


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
    """Parse rollback summary validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Developer Workflow local rollback summary packet.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--proof-report", default=str(DEFAULT_PROOF_REPORT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for rollback summary packet validation."""

    args = parse_args(argv)
    validation = validate_developer_workflow_local_rollback_summary_packet(
        schema_path=Path(args.schema),
        packet_path=Path(args.packet),
        proof_report_path=Path(args.proof_report),
    )
    write_developer_workflow_local_rollback_summary_packet_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("DEVELOPER WORKFLOW LOCAL ROLLBACK SUMMARY PACKET VALID")
    else:
        print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK SUMMARY PACKET INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
