#!/usr/bin/env python3
"""Validate the operator control tower status receipt.

Purpose: prove the dashboard focus export is a projection-only, hash-bound
receipt that can be checked without booting the gateway test client.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: operator control tower receipt schema, control tower builder, and
schema validator.
Invariants:
  - The receipt never grants execution authority or external effects.
  - The receipt hash is deterministic and excludes the derived receipt id.
  - Sandbox-to-PR focus is causally consistent with the blocker.
  - Workflow receipt counts cannot overclaim completed evidence.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from gateway.command_spine import canonical_hash  # noqa: E402
from gateway.operator_control_tower import (  # noqa: E402
    OperatorControlTowerBuilder,
    OperatorPanelKind,
    operator_control_tower_status_receipt,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "operator_control_tower_status_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "operator_control_tower_status_receipt_validation.json"
DEFAULT_GENERATED_AT = "2026-05-06T12:00:00Z"
STATUS_BLOCKER = {
    "awaiting_receipts": "sandbox_receipts_incomplete",
    "awaiting_operator_approval": "operator_approval_missing",
    "ready_to_prepare_pr": "pr_candidate_not_prepared",
    "pr_candidate_ready": "none",
    "unknown": "unknown",
}
BLOCKER_FOCUS = {
    "capability_policy_incomplete": "capability_passports",
    "sandbox_receipts_incomplete": {
        "sandbox_patch_receipt",
        "test_gate_receipt",
        "diff_review_receipt",
        "terminal_receipt",
    },
    "operator_approval_missing": "operator_approval",
    "pr_candidate_not_prepared": "pr_candidate",
    "none": "none",
    "unknown": "none",
}
CANONICAL_SANDBOX_RECEIPT_ACTIONS = {
    "sandbox_patch_receipt": "attach before state, after state, diff, command, and rollback receipt",
    "test_gate_receipt": "attach bounded local test command receipt and observed result",
    "diff_review_receipt": "attach reviewed diff hash and reviewer evidence reference",
    "terminal_receipt": "attach final local receipt summary and no-external-effect witness",
}


@dataclass(frozen=True, slots=True)
class OperatorControlTowerStatusReceiptValidation:
    """Validation report for the control tower status receipt."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    receipt_path: str
    receipt_id: str
    blocker: str
    focus_id: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_default_operator_control_tower_status_receipt() -> dict[str, Any]:
    """Build the canonical Foundation Mode dashboard status receipt."""

    builder = OperatorControlTowerBuilder()
    for panel in OperatorPanelKind:
        builder.attach_panel(panel, _panel_read_model(panel.value, item_count=1))
    builder.attach_panel(
        OperatorPanelKind.CAPABILITY_HEALTH,
        _panel_read_model("capability_friction_control", item_count=6)
        | {
            "metadata": {
                "developer_workflow_summary": {
                    "task": "Mullu Developer Workflow v1",
                    "status": "preflight_ready",
                    "reason": "local lab workflow can prepare sandbox diff and receipt",
                    "next_unlock": "approval",
                    "action_needed": "attach sandbox receipts",
                },
            },
        },
    )
    builder.attach_panel(
        OperatorPanelKind.WORKFLOW_MONITOR,
        _panel_read_model("operator_workflow_monitor", item_count=1)
        | {
            "metadata": {
                "sandbox_to_pr_packet": {
                    "status": "awaiting_receipts",
                    "blocker": "sandbox_receipts_incomplete",
                    "next_action": "complete sandbox patch, test, diff, and terminal receipts",
                },
                "sandbox_to_pr_focus": {
                    "focus_id": "sandbox_patch_receipt",
                    "label": "Sandbox patch receipt",
                    "status": "pending",
                    "action": "attach before state, after state, diff, command, and rollback receipt",
                    "source": (
                        "workflow_monitor.metadata.developer_workflow_run.receipt_checklist."
                        "sandbox_patch_receipt"
                    ),
                    "next_action": "complete sandbox patch, test, diff, and terminal receipts",
                    "blocker": "sandbox_receipts_incomplete",
                },
                "developer_workflow_run": {
                    "status": "waiting_for_approval",
                    "current_task_id": "sandbox_change",
                    "receipt_checklist_required_count": 6,
                    "receipt_checklist_completed_required_count": 0,
                    "rollback_receipt_status": "not_recorded",
                },
            },
        },
    )
    snapshot = builder.build(tenant_id="operator", generated_at=DEFAULT_GENERATED_AT)
    return operator_control_tower_status_receipt(snapshot)


def validate_operator_control_tower_status_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_path: Path | None = None,
) -> OperatorControlTowerStatusReceiptValidation:
    """Validate schema and semantic consistency for a status receipt."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator control tower status receipt schema", errors)
    if receipt_path is None:
        receipt = build_default_operator_control_tower_status_receipt()
        receipt_label = "<generated>"
    else:
        receipt = _load_json_object(receipt_path, "operator control tower status receipt", errors)
        receipt_label = _path_label(receipt_path)
    if schema and receipt:
        errors.extend(f"{receipt_label}: {error}" for error in _validate_schema_instance(schema, receipt))
        _validate_receipt_semantics(receipt, errors, receipt_label)
    sandbox_to_pr = receipt.get("sandbox_to_pr", {}) if isinstance(receipt, Mapping) else {}
    focus = sandbox_to_pr.get("focus", {}) if isinstance(sandbox_to_pr, Mapping) else {}
    return OperatorControlTowerStatusReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        receipt_path=receipt_label,
        receipt_id=str(receipt.get("receipt_id", "")) if isinstance(receipt, Mapping) else "",
        blocker=str(sandbox_to_pr.get("blocker", "")) if isinstance(sandbox_to_pr, Mapping) else "",
        focus_id=str(focus.get("focus_id", "")) if isinstance(focus, Mapping) else "",
    )


def write_operator_control_tower_status_receipt_validation(
    validation: OperatorControlTowerStatusReceiptValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic status receipt validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_default_operator_control_tower_status_receipt(output_path: Path) -> Path:
    """Write the generated canonical status receipt for inspection."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_default_operator_control_tower_status_receipt(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_receipt_semantics(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    if receipt.get("projection_only") is not True:
        errors.append(f"{label}: projection_only must be true")
    if receipt.get("external_effects_allowed") is not False:
        errors.append(f"{label}: external_effects_allowed must be false")
    _validate_receipt_hash(receipt, errors, label)
    _validate_sandbox_to_pr(receipt, errors, label)
    _validate_workflow_run(receipt, errors, label)


def _validate_receipt_hash(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    observed_hash = str(receipt.get("receipt_hash") or "")
    hash_payload = dict(receipt)
    hash_payload.pop("receipt_id", None)
    hash_payload["receipt_hash"] = ""
    expected_hash = canonical_hash(hash_payload)
    if observed_hash != expected_hash:
        errors.append(f"{label}: receipt_hash must match canonical receipt payload")
    expected_receipt_id = f"operator-control-tower-status-{observed_hash[:16]}"
    if receipt.get("receipt_id") != expected_receipt_id:
        errors.append(f"{label}: receipt_id must derive from receipt_hash")


def _validate_sandbox_to_pr(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    sandbox_to_pr = receipt.get("sandbox_to_pr")
    if not isinstance(sandbox_to_pr, Mapping):
        errors.append(f"{label}: sandbox_to_pr must be an object")
        return
    focus = sandbox_to_pr.get("focus")
    if not isinstance(focus, Mapping):
        errors.append(f"{label}: sandbox_to_pr.focus must be an object")
        return
    status = str(sandbox_to_pr.get("status") or "")
    blocker = str(sandbox_to_pr.get("blocker") or "")
    focus_id = str(focus.get("focus_id") or "")
    expected_blocker = STATUS_BLOCKER.get(status)
    if expected_blocker and blocker != expected_blocker:
        errors.append(f"{label}: sandbox_to_pr.status and blocker are inconsistent")
    focus_rule = BLOCKER_FOCUS.get(blocker)
    if isinstance(focus_rule, set):
        if focus_id not in focus_rule:
            errors.append(f"{label}: sandbox_to_pr.focus_id must identify a pending sandbox receipt")
    elif focus_rule and focus_id != focus_rule:
        errors.append(f"{label}: sandbox_to_pr.focus_id must be {focus_rule!r} for blocker {blocker!r}")
    if focus.get("blocker") != blocker:
        errors.append(f"{label}: sandbox_to_pr.focus.blocker must match sandbox_to_pr.blocker")
    if focus.get("next_action") != sandbox_to_pr.get("next_action"):
        errors.append(f"{label}: sandbox_to_pr.focus.next_action must match sandbox_to_pr.next_action")
    expected_action = CANONICAL_SANDBOX_RECEIPT_ACTIONS.get(focus_id)
    if expected_action is not None and focus.get("action") != expected_action:
        errors.append(f"{label}: sandbox_to_pr.focus.action must match canonical receipt action")
    if expected_action is None and focus.get("action") != sandbox_to_pr.get("next_action"):
        errors.append(f"{label}: sandbox_to_pr.focus.action must match sandbox_to_pr.next_action")
    if blocker != "none" and focus.get("status") != "pending":
        errors.append(f"{label}: sandbox_to_pr.focus.status must be pending while blocker is active")


def _validate_workflow_run(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    workflow_run = receipt.get("workflow_run")
    if not isinstance(workflow_run, Mapping):
        errors.append(f"{label}: workflow_run must be an object")
        return
    required_count = int(workflow_run.get("receipt_checklist_required_count", 0) or 0)
    completed_count = int(workflow_run.get("receipt_checklist_completed_required_count", 0) or 0)
    if completed_count > required_count:
        errors.append(f"{label}: workflow_run completed receipt count cannot exceed required count")


def _panel_read_model(source_surface: str, *, item_count: int) -> dict[str, object]:
    return {
        "source_surface": source_surface,
        "item_count": item_count,
        "freshness_seconds": 30,
        "signal_count": 0,
        "blocked_count": 0,
        "review_count": 0,
        "evidence_refs": ("witness:ok",),
        "raw_tool_surface_exposed": False,
        "metadata": {"owner": "operator"},
    }


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
    """Parse operator control tower status receipt validation arguments."""

    parser = argparse.ArgumentParser(description="Validate operator control tower status receipt.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipt", default="")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write-default-receipt", default="")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for status receipt validation."""

    args = parse_args(argv)
    if args.write_default_receipt:
        write_default_operator_control_tower_status_receipt(Path(args.write_default_receipt))
    validation = validate_operator_control_tower_status_receipt(
        schema_path=Path(args.schema),
        receipt_path=Path(args.receipt) if args.receipt else None,
    )
    write_operator_control_tower_status_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("OPERATOR CONTROL TOWER STATUS RECEIPT VALID")
    else:
        print(f"OPERATOR CONTROL TOWER STATUS RECEIPT INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
