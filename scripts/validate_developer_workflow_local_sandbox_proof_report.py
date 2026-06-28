#!/usr/bin/env python3
"""Validate the Developer Workflow local sandbox proof report.

Purpose: prove the one-command local proof runner report is schema-valid,
bounded to local evidence, and does not claim execution or external effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: local sandbox proof report schema and schema validator.
Invariants:
  - Reports never grant execution authority or external effects.
  - Attachment and bundle statuses match receipt counts.
  - Ready-for-external status requires command preview but still no execution.
  - Generated artifact keys are complete and path-like.
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

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "developer_workflow_local_sandbox_proof_report.schema.json"
DEFAULT_REPORT = REPO_ROOT / "examples" / "developer_workflow_local_sandbox_proof_report.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_local_sandbox_proof_report_validation.json"
REQUIRED_ARTIFACT_KEYS = (
    "sandbox_to_pr_packet",
    "sandbox_receipt_attachment_packet",
    "approval_packet",
    "local_candidate",
    "pr_tool_admission",
    "external_approval_witness",
    "command_preview",
    "metadata",
    "pr_readiness_bundle",
    "operator_receipt",
)


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowLocalSandboxProofReportValidation:
    """Validation report for the local sandbox proof report."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    report_path: str
    bundle_status: str
    attachment_packet_status: str
    pr_readiness_status: str
    completed_count: int
    required_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_developer_workflow_local_sandbox_proof_report(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    report_path: Path = DEFAULT_REPORT,
) -> DeveloperWorkflowLocalSandboxProofReportValidation:
    """Validate schema and semantic consistency for a local proof report."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "local sandbox proof report schema", errors)
    report = _load_json_object(report_path, "local sandbox proof report", errors)
    label = _path_label(report_path)
    if schema and report:
        errors.extend(f"{label}: {error}" for error in _validate_schema_instance(schema, report))
        _validate_report_semantics(report, errors, label)
    return DeveloperWorkflowLocalSandboxProofReportValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        report_path=label,
        bundle_status=str(report.get("bundle_status", "")) if isinstance(report, Mapping) else "",
        attachment_packet_status=str(report.get("attachment_packet_status", "")) if isinstance(report, Mapping) else "",
        pr_readiness_status=str(report.get("pr_readiness_status", "")) if isinstance(report, Mapping) else "",
        completed_count=int(report.get("completed_count", 0) or 0) if isinstance(report, Mapping) else 0,
        required_count=int(report.get("required_count", 0) or 0) if isinstance(report, Mapping) else 0,
    )


def write_developer_workflow_local_sandbox_proof_report_validation(
    validation: DeveloperWorkflowLocalSandboxProofReportValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic local proof report validation record."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_report_semantics(report: Mapping[str, Any], errors: list[str], label: str) -> None:
    if report.get("external_effects_allowed") is not False:
        errors.append(f"{label}: external_effects_allowed must be false")
    if report.get("execution_performed") is not False:
        errors.append(f"{label}: execution_performed must be false")
    completed_count = int(report.get("completed_count", -1) or 0)
    required_count = int(report.get("required_count", -1) or 0)
    if completed_count > required_count:
        errors.append(f"{label}: completed_count cannot exceed required_count")
    expected_bundle_status = "receipts_complete" if completed_count == required_count and required_count > 0 else "awaiting_receipts"
    if report.get("ok") is False:
        expected_bundle_status = "unknown"
    if report.get("bundle_status") != expected_bundle_status:
        errors.append(f"{label}: bundle_status must match completed receipt count")
    expected_attachment_status = (
        "attachments_complete" if completed_count == required_count and required_count > 0 else "awaiting_attachments"
    )
    if report.get("ok") is False:
        expected_attachment_status = "unknown"
    if report.get("attachment_packet_status") != expected_attachment_status:
        errors.append(f"{label}: attachment_packet_status must match completed receipt count")
    next_attachment = str(report.get("next_attachment_id") or "")
    if expected_attachment_status == "attachments_complete" and next_attachment != "none":
        errors.append(f"{label}: next_attachment_id must be 'none' when attachments are complete")
    if expected_attachment_status == "awaiting_attachments" and next_attachment == "none":
        errors.append(f"{label}: next_attachment_id cannot be 'none' while attachments are pending")
    ready_for_external = report.get("ready_for_external_pr_execution") is True
    command_preview = report.get("command_preview_rendered") is True
    pr_status = str(report.get("pr_readiness_status") or "")
    if ready_for_external and pr_status != "ready_for_external_pr_execution":
        errors.append(f"{label}: ready_for_external_pr_execution requires matching pr_readiness_status")
    if pr_status == "ready_for_external_pr_execution" and not command_preview:
        errors.append(f"{label}: ready_for_external_pr_execution requires command_preview_rendered")
    if not _url_has_local_opt_in(str(report.get("control_tower_url") or "")):
        errors.append(f"{label}: control_tower_url must include local sandbox receipt opt-in")
    if not _url_has_local_opt_in(str(report.get("workflow_read_model_url") or "")):
        errors.append(f"{label}: workflow_read_model_url must include local sandbox receipt opt-in")
    artifacts = report.get("generated_artifacts")
    if not isinstance(artifacts, Mapping):
        errors.append(f"{label}: generated_artifacts must be an object")
        return
    require_artifacts = report.get("ok") is True
    for artifact_key in REQUIRED_ARTIFACT_KEYS:
        artifact_path = str(artifacts.get(artifact_key) or "")
        if not artifact_path:
            if require_artifacts:
                errors.append(f"{label}: generated_artifacts.{artifact_key} is required")
        elif _looks_external(artifact_path):
            errors.append(f"{label}: generated_artifacts.{artifact_key} must be workspace-local")


def _url_has_local_opt_in(value: str) -> bool:
    return "include_local_sandbox_receipts=true" in value


def _looks_external(value: str) -> bool:
    lowered = value.lower()
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
    """Parse local sandbox proof report validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Developer Workflow local sandbox proof report.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for local sandbox proof report validation."""

    args = parse_args(argv)
    validation = validate_developer_workflow_local_sandbox_proof_report(
        schema_path=Path(args.schema),
        report_path=Path(args.report),
    )
    write_developer_workflow_local_sandbox_proof_report_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("DEVELOPER WORKFLOW LOCAL SANDBOX PROOF REPORT VALID")
    else:
        print(f"DEVELOPER WORKFLOW LOCAL SANDBOX PROOF REPORT INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
