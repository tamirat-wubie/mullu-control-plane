#!/usr/bin/env python3
"""Validate the Developer Workflow local rollback execution receipt.

Purpose: prove local rollback execution receipts are schema-valid, approval
bound, workspace-bound, and internally consistent.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: rollback execution receipt schema and workspace schema validator.
Invariants:
  - External effects are always false.
  - Execution can be claimed only in execute mode with approved deletion.
  - Every artifact row records boundary, pre-state, post-state, and outcome.
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


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "developer_workflow_local_rollback_execution_receipt.schema.json"
DEFAULT_RECEIPT = REPO_ROOT / "examples" / "developer_workflow_local_rollback_execution_receipt.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_execution_receipt_validation.json"


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowLocalRollbackExecutionReceiptValidation:
    """Validation report for the local rollback execution receipt."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    receipt_path: str
    execution_status: str
    execution_mode: str
    executed_artifact_count: int
    failed_artifact_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_developer_workflow_local_rollback_execution_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_path: Path = DEFAULT_RECEIPT,
) -> DeveloperWorkflowLocalRollbackExecutionReceiptValidation:
    """Validate schema and semantic consistency for a rollback execution receipt."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "rollback execution schema", errors)
    receipt = _load_json_object(receipt_path, "rollback execution receipt", errors)
    receipt_label = _path_label(receipt_path)
    if schema and receipt:
        errors.extend(f"{receipt_label}: {error}" for error in _validate_schema_instance(schema, receipt))
    if receipt:
        _validate_receipt_semantics(receipt, errors, receipt_label)
    return DeveloperWorkflowLocalRollbackExecutionReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        receipt_path=receipt_label,
        execution_status=str(receipt.get("execution_status", "")) if isinstance(receipt, Mapping) else "",
        execution_mode=str(receipt.get("execution_mode", "")) if isinstance(receipt, Mapping) else "",
        executed_artifact_count=int(receipt.get("executed_artifact_count", 0) or 0)
        if isinstance(receipt, Mapping)
        else 0,
        failed_artifact_count=int(receipt.get("failed_artifact_count", 0) or 0)
        if isinstance(receipt, Mapping)
        else 0,
    )


def write_developer_workflow_local_rollback_execution_receipt_validation(
    validation: DeveloperWorkflowLocalRollbackExecutionReceiptValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic rollback execution receipt validation record."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_receipt_semantics(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    if receipt.get("external_effects_allowed") is not False:
        errors.append(f"{label}: external_effects_allowed must be false")
    if receipt.get("target_path_checks_performed") is not True:
        errors.append(f"{label}: target_path_checks_performed must be true")
    artifacts = receipt.get("artifacts", ())
    if not isinstance(artifacts, list):
        errors.append(f"{label}: artifacts must be a list")
        artifacts = []
    executed_count = sum(1 for item in artifacts if isinstance(item, Mapping) and item.get("action_status") == "deleted")
    failed_count = sum(
        1
        for item in artifacts
        if isinstance(item, Mapping) and item.get("action_status") in {"boundary_blocked", "failed"}
    )
    skipped_count = len([item for item in artifacts if isinstance(item, Mapping)]) - executed_count - failed_count
    if int(receipt.get("executed_artifact_count", -1) or 0) != executed_count:
        errors.append(f"{label}: executed_artifact_count must match deleted rows")
    if int(receipt.get("failed_artifact_count", -1) or 0) != failed_count:
        errors.append(f"{label}: failed_artifact_count must match failed rows")
    if int(receipt.get("skipped_artifact_count", -1) or 0) != skipped_count:
        errors.append(f"{label}: skipped_artifact_count must match non-deleted non-failed rows")
    execution_mode = str(receipt.get("execution_mode") or "")
    approved = receipt.get("approval_status") == "approved" and receipt.get("delete_execution_allowed") is True
    performed = receipt.get("rollback_execution_performed") is True
    if performed and execution_mode != "execute":
        errors.append(f"{label}: rollback_execution_performed requires execute mode")
    if performed and not approved:
        errors.append(f"{label}: rollback_execution_performed requires approved deletion authority")
    if performed and executed_count == 0:
        errors.append(f"{label}: rollback_execution_performed requires at least one deleted artifact")
    expected_status = _expected_status(
        approved=approved,
        execution_mode=execution_mode,
        executed_count=executed_count,
        failed_count=failed_count,
        selected_count=int(receipt.get("selected_artifact_count", 0) or 0),
    )
    if receipt.get("execution_status") != expected_status:
        errors.append(f"{label}: execution_status must match observed artifact outcomes")
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            errors.append(f"{label}: artifact row must be an object")
            continue
        artifact_id = str(artifact.get("artifact_id") or "")
        action_status = str(artifact.get("action_status") or "")
        if artifact.get("required_confirmation") is not True:
            errors.append(f"{label}: artifact {artifact_id} required_confirmation must be true")
        if artifact.get("path_within_workspace") is not True and action_status not in {"boundary_blocked", "skipped"}:
            errors.append(f"{label}: artifact {artifact_id} outside workspace must be blocked or skipped")
        if action_status == "deleted" and artifact.get("post_exists") is not False:
            errors.append(f"{label}: artifact {artifact_id} deleted row must have post_exists false")
        if action_status == "would_delete" and execution_mode != "dry_run":
            errors.append(f"{label}: artifact {artifact_id} would_delete is valid only in dry_run mode")


def _expected_status(
    *,
    approved: bool,
    execution_mode: str,
    executed_count: int,
    failed_count: int,
    selected_count: int,
) -> str:
    if not approved:
        return "blocked_no_approval"
    if execution_mode == "dry_run":
        return "dry_run_ready" if selected_count else "blocked_no_approval"
    if failed_count and executed_count:
        return "rollback_partial"
    if failed_count:
        return "rollback_failed"
    if executed_count:
        return "rollback_executed"
    return "rollback_noop"


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
    """Parse rollback execution receipt validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Developer Workflow local rollback execution receipt.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for rollback execution receipt validation."""

    args = parse_args(argv)
    validation = validate_developer_workflow_local_rollback_execution_receipt(
        schema_path=Path(args.schema),
        receipt_path=Path(args.receipt),
    )
    write_developer_workflow_local_rollback_execution_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("DEVELOPER WORKFLOW LOCAL ROLLBACK EXECUTION RECEIPT VALID")
    else:
        print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK EXECUTION RECEIPT INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
