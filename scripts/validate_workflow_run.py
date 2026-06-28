#!/usr/bin/env python3
"""Validate the Mullusi causal workflow run contract.

Purpose: verify workflow-run schema shape, fixture closure, risk routing,
approval, rollback, receipt, validation, and monitoring invariants.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, and PRS for WorkflowRun.
Dependencies: Python standard library and scripts.validate_schemas.
Invariants:
  - Read-only R0/R1 runs may close without approval when evidence and receipts exist.
  - R3/R4 runs cannot pass the approval gate without approval refs.
  - Closed runs require validated goal satisfaction and receipt evidence.
  - External effects require rollback or compensation readiness before execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "workflow_run.schema.json"
FIXTURE_PATH = WORKSPACE_ROOT / "examples" / "workflow_run_governed_work_assistant_demo_v0.foundation.json"
HIGH_RISK_CLASSES = {"R3", "R4"}
APPROVAL_PASSED_STATES = {
    "APPROVED",
    "EXECUTING",
    "OBSERVED",
    "VALIDATED",
    "RECEIPTED",
    "CLOSED",
    "ROLLED_BACK",
}
TERMINAL_STATES = {"CLOSED", "ROLLED_BACK"}
PROHIBITED_PRIVATE_REASONING_FIELDS = {
    "chain_of_thought",
    "raw_chain_of_thought",
    "private_reasoning",
    "hidden_reasoning",
    "scratchpad",
}


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load a JSON object from a workspace-local artifact."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {_relative(json_path)}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_workflow_run_record(record: dict[str, Any]) -> list[str]:
    """Validate one workflow-run record against schema and lifecycle invariants."""

    schema = _load_schema(SCHEMA_PATH)
    errors = [f"schema: {error}" for error in _validate_schema_instance(schema, record)]
    errors.extend(_validate_no_private_reasoning_fields(record, "workflow_run"))
    errors.extend(_validate_task_bindings(record))
    errors.extend(_validate_lifecycle_invariants(record))
    return errors


def validate_contract(payload_path: Path = FIXTURE_PATH) -> list[str]:
    """Validate the canonical workflow-run fixture."""

    record = load_json_object(payload_path, "workflow run fixture")
    return validate_workflow_run_record(record)


def build_validation_report(payload_path: Path = FIXTURE_PATH) -> dict[str, Any]:
    """Build a machine-readable workflow-run validation receipt."""

    try:
        errors = validate_contract(payload_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [f"load-workflow-run-contract: {_sanitize_error(exc)}"]
    valid = not errors
    checks = (
        "workflow_run_schema_contract",
        "workflow_run_fixture_contract",
        "workflow_run_task_binding",
        "workflow_run_risk_class_approval_gate",
        "workflow_run_false_success_block",
        "workflow_run_external_effect_rollback_gate",
        "workflow_run_receipt_before_closure",
        "workflow_run_monitoring_state",
    )
    return {
        "receipt_id": "workflow_run_validation_receipt",
        "valid": valid,
        "status": "passed" if valid else "failed",
        "schema_path": _relative(SCHEMA_PATH),
        "payload_path": _relative(payload_path),
        "checks": [{"name": check_name, "passed": valid} for check_name in checks],
        "check_count": len(checks),
        "error_count": len(errors),
        "errors": errors,
    }


def _validate_lifecycle_invariants(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lifecycle_state = str(record.get("lifecycle_state") or "")
    risk_class = str(record.get("risk_class") or "")
    approval_refs = _text_refs(record.get("approval_refs"))
    receipt_refs = _text_refs(record.get("receipt_refs"))
    boundary = record.get("boundary") if isinstance(record.get("boundary"), dict) else {}
    action_plan = record.get("action_plan") if isinstance(record.get("action_plan"), dict) else {}
    rollback_plan = record.get("rollback_plan") if isinstance(record.get("rollback_plan"), dict) else {}
    validation = record.get("validation_result") if isinstance(record.get("validation_result"), dict) else {}
    monitoring = record.get("monitoring_state") if isinstance(record.get("monitoring_state"), dict) else {}

    external_effect = (
        risk_class in HIGH_RISK_CLASSES
        or boundary.get("external_effects_allowed") is True
        or action_plan.get("external_effects_allowed") is True
    )
    if risk_class == "R5" and lifecycle_state not in {"BLOCKED", "FAILED"}:
        errors.append("workflow_run: R5 prohibited action must be BLOCKED or FAILED")
    if risk_class in HIGH_RISK_CLASSES and lifecycle_state in APPROVAL_PASSED_STATES and not approval_refs:
        errors.append("workflow_run: high-risk action cannot pass approval gate without approval_refs")
    if external_effect:
        if rollback_plan.get("rollback_required") is not True:
            errors.append("workflow_run: external effect requires rollback_required true")
        rollback_refs = _text_refs(rollback_plan.get("rollback_refs"))
        compensating_action = str(rollback_plan.get("compensating_action") or "")
        if rollback_plan.get("rollback_ready") is not True:
            errors.append("workflow_run: external effect requires rollback_ready true")
        if rollback_plan.get("reversibility_label") == "UNKNOWN":
            errors.append("workflow_run: external effect cannot use UNKNOWN reversibility")
        if not rollback_refs and not compensating_action:
            errors.append("workflow_run: external effect requires rollback_refs or compensating_action")
        if monitoring.get("monitoring_required") is not True:
            errors.append("workflow_run: external effect requires monitoring_required true")

    if lifecycle_state in TERMINAL_STATES and not receipt_refs:
        errors.append("workflow_run: terminal closure requires receipt_refs")
    if lifecycle_state == "CLOSED":
        required_true_fields = (
            "goal_satisfied",
            "constraints_respected",
            "evidence_attached",
            "receipt_emitted",
            "rollback_state_known",
            "monitoring_handled",
        )
        for field_name in required_true_fields:
            if validation.get(field_name) is not True:
                errors.append(f"workflow_run: CLOSED requires validation_result.{field_name} true")
        if validation.get("status") != "PASS":
            errors.append("workflow_run: CLOSED requires validation_result.status PASS")
    return errors


def _validate_task_bindings(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tasks = record.get("tasks") if isinstance(record.get("tasks"), list) else []
    task_runs = record.get("task_runs") if isinstance(record.get("task_runs"), list) else []
    task_ids = [str(task.get("task_id") or "") for task in tasks if isinstance(task, dict)]
    task_run_ids = [str(task_run.get("task_id") or "") for task_run in task_runs if isinstance(task_run, dict)]
    if set(task_ids) != set(task_run_ids):
        errors.append("workflow_run: task_runs must match tasks by task_id")
    if len(task_ids) != len(set(task_ids)):
        errors.append("workflow_run: task_id values must be unique")
    known_task_ids = set(task_ids)
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("task_id") or "")
        for dependency_id in _text_refs(task.get("depends_on")):
            if dependency_id not in known_task_ids:
                errors.append(f"workflow_run: task {task_id} depends on unknown task {dependency_id}")
    return errors


def _validate_no_private_reasoning_fields(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in PROHIBITED_PRIVATE_REASONING_FIELDS:
                errors.append(f"{path}.{key} is prohibited")
            errors.extend(_validate_no_private_reasoning_fields(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_validate_no_private_reasoning_fields(child, f"{path}[{index}]"))
    return errors


def _text_refs(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _relative(path: Path) -> str:
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _sanitize_error(exc: BaseException) -> str:
    message = str(exc)
    for path in (SCHEMA_PATH, FIXTURE_PATH):
        message = message.replace(str(path), _relative(path))
        message = message.replace(str(path.resolve(strict=False)), _relative(path))
    return message


def main(argv: list[str] | None = None) -> int:
    """Validate workflow-run contract artifacts."""

    parser = argparse.ArgumentParser(description="Validate governed WorkflowRun artifacts.")
    parser.add_argument("--payload", type=Path, default=FIXTURE_PATH, help="workflow-run payload to validate")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)

    payload_path = args.payload if args.payload.is_absolute() else WORKSPACE_ROOT / args.payload
    report = build_validation_report(payload_path)
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0 if report["valid"] else 1
    if not report["valid"]:
        for error in report["errors"]:
            sys.stderr.write(f"[FAIL] workflow-run: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1
    for check in report["checks"]:
        sys.stdout.write(f"[PASS] {check['name']}\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
