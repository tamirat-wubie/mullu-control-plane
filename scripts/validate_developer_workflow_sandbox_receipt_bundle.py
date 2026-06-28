#!/usr/bin/env python3
"""Validate the Developer Workflow v1 sandbox receipt bundle.

Purpose: prove the local lab receipt bundle has explicit sandbox patch, test,
diff, and terminal receipt slots before PR preparation can claim readiness.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: sandbox receipt bundle schema, fixture, and schema validator.
Invariants:
  - The bundle never grants external effects.
  - Receipt ids, sources, and stages are canonical and ordered.
  - Pending receipts use pending placeholders; complete receipts carry evidence.
  - Completed count matches receipt status.
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

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "developer_workflow_sandbox_receipt_bundle.schema.json"
DEFAULT_BUNDLE = REPO_ROOT / "examples" / "developer_workflow_sandbox_receipt_bundle.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_sandbox_receipt_bundle_validation.json"
EXPECTED_RECEIPTS = (
    ("sandbox_patch_receipt", "Sandbox patch receipt", "write_files_in_sandbox"),
    ("test_gate_receipt", "Test gate receipt", "run_tests"),
    ("diff_review_receipt", "Diff review receipt", "show_diff"),
    ("terminal_receipt", "Terminal receipt", "show_receipt"),
)
PENDING_PLACEHOLDER_FIELDS = ("before_state_hash", "after_state_hash", "diff_hash", "rollback_command", "command")


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowSandboxReceiptBundleValidation:
    """Validation report for the Developer Workflow sandbox receipt bundle."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    bundle_path: str
    bundle_status: str
    completed_count: int
    required_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_developer_workflow_sandbox_receipt_bundle(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    bundle_path: Path = DEFAULT_BUNDLE,
) -> DeveloperWorkflowSandboxReceiptBundleValidation:
    """Validate schema and local-lab receipt bundle semantics."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "sandbox receipt bundle schema", errors)
    bundle = _load_json_object(bundle_path, "sandbox receipt bundle", errors)
    if schema and bundle:
        errors.extend(f"{_path_label(bundle_path)}: {error}" for error in _validate_schema_instance(schema, bundle))
        _validate_bundle_semantics(bundle, errors, _path_label(bundle_path))
    return DeveloperWorkflowSandboxReceiptBundleValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        bundle_path=_path_label(bundle_path),
        bundle_status=str(bundle.get("bundle_status", "")) if isinstance(bundle, Mapping) else "",
        completed_count=int(bundle.get("completed_count", 0) or 0) if isinstance(bundle, Mapping) else 0,
        required_count=int(bundle.get("required_count", 0) or 0) if isinstance(bundle, Mapping) else 0,
    )


def write_developer_workflow_sandbox_receipt_bundle_validation(
    validation: DeveloperWorkflowSandboxReceiptBundleValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic validation report for the bundle."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_bundle_semantics(bundle: Mapping[str, Any], errors: list[str], label: str) -> None:
    if bundle.get("external_effects_allowed") is not False:
        errors.append(f"{label}: external_effects_allowed must remain false")
    if bundle.get("execution_boundary") != "local_lab_only":
        errors.append(f"{label}: execution_boundary must be local_lab_only")
    if bundle.get("rollback_default") is not True:
        errors.append(f"{label}: rollback_default must remain true")
    receipts = bundle.get("receipts")
    if not isinstance(receipts, list):
        errors.append(f"{label}: receipts must be a list")
        return
    _validate_receipt_order(receipts, errors, label)
    completed_count = sum(1 for receipt in receipts if isinstance(receipt, Mapping) and receipt.get("status") == "complete")
    if int(bundle.get("completed_count", -1) or 0) != completed_count:
        errors.append(f"{label}: completed_count must match complete receipts")
    expected_status = "receipts_complete" if completed_count == len(EXPECTED_RECEIPTS) else "awaiting_receipts"
    if bundle.get("bundle_status") != expected_status:
        errors.append(f"{label}: bundle_status must be {expected_status!r}")
    for receipt in receipts:
        if isinstance(receipt, Mapping):
            _validate_receipt(receipt, errors, label)


def _validate_receipt_order(receipts: list[object], errors: list[str], label: str) -> None:
    observed = tuple(str(item.get("receipt_id", "")) for item in receipts if isinstance(item, Mapping))
    expected = tuple(item[0] for item in EXPECTED_RECEIPTS)
    if observed != expected:
        errors.append(f"{label}: receipts must list canonical receipt ids in order")
    if len(set(observed)) != len(observed):
        errors.append(f"{label}: receipt ids must be unique")


def _validate_receipt(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipt_id = str(receipt.get("receipt_id", ""))
    expected_by_id = {item[0]: item for item in EXPECTED_RECEIPTS}
    expected = expected_by_id.get(receipt_id)
    if expected is None:
        errors.append(f"{label}: unknown receipt_id {receipt_id!r}")
        return
    _, expected_label, expected_stage = expected
    if receipt.get("label") != expected_label:
        errors.append(f"{label}: {receipt_id} label must be {expected_label!r}")
    if receipt.get("stage") != expected_stage:
        errors.append(f"{label}: {receipt_id} stage must be {expected_stage!r}")
    expected_source = f"workflow_monitor.metadata.developer_workflow_run.receipt_checklist.{receipt_id}"
    if receipt.get("source") != expected_source:
        errors.append(f"{label}: {receipt_id} source must be {expected_source!r}")
    if receipt.get("required") is not True:
        errors.append(f"{label}: {receipt_id} must remain required")
    status = str(receipt.get("status", ""))
    evidence_refs = receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        errors.append(f"{label}: {receipt_id} evidence_refs must be a list")
        return
    if status == "pending":
        _validate_pending_receipt(receipt, receipt_id, errors, label)
    elif status == "complete":
        _validate_complete_receipt(receipt, receipt_id, errors, label)


def _validate_pending_receipt(
    receipt: Mapping[str, Any],
    receipt_id: str,
    errors: list[str],
    label: str,
) -> None:
    if receipt.get("evidence_refs") != []:
        errors.append(f"{label}: {receipt_id} pending evidence_refs must be empty")
    for field_name in PENDING_PLACEHOLDER_FIELDS:
        if receipt.get(field_name) != "pending":
            errors.append(f"{label}: {receipt_id}.{field_name} must be pending until receipt completion")


def _validate_complete_receipt(
    receipt: Mapping[str, Any],
    receipt_id: str,
    errors: list[str],
    label: str,
) -> None:
    evidence_refs = receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append(f"{label}: {receipt_id} complete evidence_refs must be non-empty")
    for field_name in PENDING_PLACEHOLDER_FIELDS:
        if receipt.get(field_name) == "pending":
            errors.append(f"{label}: {receipt_id}.{field_name} must be concrete when complete")


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
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse sandbox receipt bundle validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Developer Workflow sandbox receipt bundle.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for sandbox receipt bundle validation."""

    args = parse_args(argv)
    validation = validate_developer_workflow_sandbox_receipt_bundle(
        schema_path=Path(args.schema),
        bundle_path=Path(args.bundle),
    )
    write_developer_workflow_sandbox_receipt_bundle_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("DEVELOPER WORKFLOW SANDBOX RECEIPT BUNDLE VALID")
    else:
        print(f"DEVELOPER WORKFLOW SANDBOX RECEIPT BUNDLE INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
