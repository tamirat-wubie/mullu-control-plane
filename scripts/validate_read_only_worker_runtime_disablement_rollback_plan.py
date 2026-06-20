#!/usr/bin/env python3
"""Validate read-only worker runtime disablement rollback plans.

Purpose: bind a Foundation Mode rollback plan for disabling read-only worker
runtime enablement without executing disablement, enabling runtime dispatch,
invoking workers, emitting receipts, appending receipts, or claiming terminal
closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: rollback plan schema and runtime enablement review packet.
Invariants:
  - The plan is evidence-bound but non-executing.
  - Runtime enablement and dispatch remain blocked.
  - Rollback execution still requires operator approval and trusted runtime
    clock evidence.
  - Mfidel atomicity is preserved.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "read_only_worker_runtime_disablement_rollback_plan.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "read_only_worker_runtime_disablement_rollback_plan.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "read_only_worker_runtime_disablement_rollback_plan_validation.json"
ROLLBACK_PLAN_ID = "read-only-worker-runtime-disablement-rollback-plan-foundation-repo-inspection-20260620"
FALSE_TOP_LEVEL_FIELDS = (
    "runtime_enablement_allowed",
    "runtime_enablement_executed",
    "runtime_dispatch_admitted",
    "runtime_dispatch_performed",
    "worker_invocation_performed",
    "runtime_disablement_executed",
    "runtime_receipt_emitted",
    "receipt_append_performed",
    "terminal_closure_performed",
    "success_claim_allowed",
    "secret_values_serialized",
    "connector_authority_allowed",
    "filesystem_write_allowed",
    "external_network_allowed",
)
TRUE_BOUNDARY_FIELDS = (
    "plan_is_not_runtime_enablement",
    "plan_is_not_runtime_dispatch",
    "plan_is_not_worker_invocation",
    "plan_is_not_disablement_execution",
    "plan_is_not_receipt_emission",
    "plan_is_not_receipt_append",
    "plan_is_not_terminal_closure",
)
BLOCKED_ACTIONS = (
    "read_only_worker_runtime_enablement",
    "read_only_worker_runtime_dispatch_admission",
    "read_only_worker_runtime_dispatch",
    "read_only_worker_invocation",
    "read_only_worker_runtime_receipt_emission",
    "read_only_worker_receipt_append",
    "read_only_worker_terminal_closure_claim",
)


@dataclass(frozen=True, slots=True)
class RuntimeDisablementRollbackPlanValidation:
    """Validation result for one runtime disablement rollback plan."""

    valid: bool
    rollback_plan_path: str
    schema_path: str
    errors: tuple[str, ...]
    rollback_step_count: int
    required_evidence_ref_count: int
    runtime_enablement_allowed: bool
    runtime_disablement_executed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_runtime_disablement_rollback_plan() -> dict[str, Any]:
    """Build the canonical non-executing runtime disablement rollback plan."""

    rollback_steps = [
        _rollback_step(
            "capture-current-runtime-state",
            1,
            "Capture runtime enablement state and active lease identifiers before any disablement attempt.",
            "read_only_worker_runtime_state_snapshot",
        ),
        _rollback_step(
            "block-new-dispatch-admission",
            2,
            "Prevent new runtime dispatch admission while preserving existing receipt evidence.",
            "read_only_worker_runtime_dispatch_admission_block_receipt",
        ),
        _rollback_step(
            "revoke-active-runtime-lease",
            3,
            "Revoke or let expire the active runtime lease through a governed lease boundary.",
            "read_only_worker_active_runtime_lease_revocation_receipt",
        ),
        _rollback_step(
            "disable-receipt-emission",
            4,
            "Disable runtime receipt emission only after dispatch admission is blocked.",
            "read_only_worker_runtime_receipt_emission_disablement_receipt",
        ),
        _rollback_step(
            "record-worker-failure-receipt",
            5,
            "Record WorkerFailureReceipt evidence when rollback is caused by failed or partial execution.",
            "worker_failure_receipt",
        ),
        _rollback_step(
            "verify-terminal-safe-state",
            6,
            "Verify no dispatch, invocation, receipt emission, or append continues after rollback.",
            "read_only_worker_runtime_rollback_verification_receipt",
        ),
    ]
    return {
        "rollback_plan_id": ROLLBACK_PLAN_ID,
        "rollback_plan_version": "read_only_worker_runtime_disablement_rollback_plan.v1",
        "selected_worker_path": "read_only_repo_inspection",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "plan_state": "plan_bound_execution_blocked",
        **{field_name: True for field_name in TRUE_BOUNDARY_FIELDS},
        **{field_name: False for field_name in FALSE_TOP_LEVEL_FIELDS},
        "disablement_triggers": [
            "runtime_dispatch_safety_violation",
            "receipt_emission_integrity_failure",
            "active_lease_boundary_violation",
            "operator_revocation_request",
        ],
        "rollback_steps": rollback_steps,
        "required_evidence_refs": [
            "examples/read_only_worker_runtime_enablement_review_packet.foundation.json",
            "examples/read_only_worker_runtime_enablement_witness.foundation.json",
            "examples/read_only_worker_active_runtime_lease_admission_witness.foundation.json",
            "examples/read_only_worker_uao_dispatch_authorization_witness.foundation.json",
            "examples/read_only_worker_phi_gov_dispatch_authorization_witness.foundation.json",
            "examples/read_only_worker_runtime_dispatch_admission_witness.foundation.json",
            "examples/read_only_worker_trusted_runtime_clock_receipt.foundation.json",
            "schemas/worker_failure_receipt.schema.json",
            "schemas/temporal_lease_window_receipt.schema.json",
        ],
        "blocked_actions": list(BLOCKED_ACTIONS),
        "recovery_state": {
            "rollback_plan_bound": True,
            "rollback_execution_allowed": False,
            "operator_reapproval_required": True,
            "worker_failure_receipt_required": True,
            "trusted_runtime_clock_required": True,
            "terminal_closure_required": True,
        },
        "validators": [
            "scripts/validate_read_only_worker_runtime_disablement_rollback_plan.py",
            "tests/test_validate_read_only_worker_runtime_disablement_rollback_plan.py",
        ],
        "next_action": (
            "Bind operator runtime enablement approval before any runtime enablement acceptance "
            "or rollback execution decision."
        ),
    }


def validate_runtime_disablement_rollback_plan(
    *,
    rollback_plan_path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> RuntimeDisablementRollbackPlanValidation:
    """Validate one read-only worker runtime disablement rollback plan."""

    errors: list[str] = []
    schema = _load_schema(schema_path)
    rollback_plan = _load_json_object(rollback_plan_path, "runtime disablement rollback plan", errors)
    expected_plan = build_runtime_disablement_rollback_plan()
    if rollback_plan:
        errors.extend(_validate_schema_instance(schema, rollback_plan))
        if rollback_plan != expected_plan:
            errors.append("runtime disablement rollback plan does not match generated plan")
        _validate_semantics(rollback_plan, errors)
    return RuntimeDisablementRollbackPlanValidation(
        valid=not errors,
        rollback_plan_path=_path_label(rollback_plan_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        rollback_step_count=len(expected_plan["rollback_steps"]),
        required_evidence_ref_count=len(expected_plan["required_evidence_refs"]),
        runtime_enablement_allowed=False,
        runtime_disablement_executed=False,
        next_action=str(expected_plan["next_action"]),
    )


def write_runtime_disablement_rollback_plan_validation(
    validation: RuntimeDisablementRollbackPlanValidation,
    output_path: Path,
) -> Path:
    """Write one rollback plan validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def write_runtime_disablement_rollback_plan_fixture(output_path: Path) -> Path:
    """Write the generated rollback plan fixture."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_runtime_disablement_rollback_plan(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _rollback_step(step_id: str, sequence: int, purpose: str, evidence_ref_required: str) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "sequence": sequence,
        "purpose": purpose,
        "required_before_execution": True,
        "execution_allowed_now": False,
        "evidence_ref_required": evidence_ref_required,
        "blocks_runtime_enablement": True,
    }


def _validate_semantics(rollback_plan: dict[str, Any], errors: list[str]) -> None:
    if rollback_plan.get("rollback_plan_id") != ROLLBACK_PLAN_ID:
        errors.append("rollback_plan_id is invalid")
    if rollback_plan.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must be AwaitingEvidence")
    if rollback_plan.get("proof_state") != "Unknown":
        errors.append("proof_state must be Unknown")
    if rollback_plan.get("plan_state") != "plan_bound_execution_blocked":
        errors.append("plan_state must be plan_bound_execution_blocked")
    for field_name in TRUE_BOUNDARY_FIELDS:
        if rollback_plan.get(field_name) is not True:
            errors.append(f"{field_name} must be true")
    for field_name in FALSE_TOP_LEVEL_FIELDS:
        if rollback_plan.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if set(_string_list(rollback_plan.get("blocked_actions"))) != set(BLOCKED_ACTIONS):
        errors.append("blocked_actions must match runtime enablement blocked actions")
    steps = rollback_plan.get("rollback_steps")
    if not isinstance(steps, list):
        errors.append("rollback_steps must be a list")
        return
    if [step.get("sequence") for step in steps if isinstance(step, dict)] != [1, 2, 3, 4, 5, 6]:
        errors.append("rollback_steps must preserve sequence 1..6")
    for step in steps:
        if not isinstance(step, dict):
            errors.append("rollback_steps entries must be objects")
            continue
        if step.get("required_before_execution") is not True:
            errors.append("rollback step required_before_execution must be true")
        if step.get("execution_allowed_now") is not False:
            errors.append("rollback step execution_allowed_now must be false")
        if step.get("blocks_runtime_enablement") is not True:
            errors.append("rollback step blocks_runtime_enablement must be true")
    recovery_state = rollback_plan.get("recovery_state")
    if not isinstance(recovery_state, dict):
        errors.append("recovery_state must be an object")
    elif recovery_state.get("rollback_execution_allowed") is not False:
        errors.append("recovery_state.rollback_execution_allowed must be false")
    for evidence_ref in _string_list(rollback_plan.get("required_evidence_refs")):
        if not (REPO_ROOT / evidence_ref).exists():
            errors.append(f"required evidence ref missing: {evidence_ref}")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing")
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
    raise ValueError(f"non-finite JSON constant is not permitted: {raw_constant}")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse rollback plan validation arguments."""

    parser = argparse.ArgumentParser(description="Validate read-only worker runtime disablement rollback plan.")
    parser.add_argument("--rollback-plan", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-fixture", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for rollback plan validation."""

    args = parse_args(argv)
    if args.write_fixture:
        write_runtime_disablement_rollback_plan_fixture(Path(args.rollback_plan))
    validation = validate_runtime_disablement_rollback_plan(
        rollback_plan_path=Path(args.rollback_plan),
        schema_path=Path(args.schema),
    )
    if args.write:
        write_runtime_disablement_rollback_plan_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("runtime disablement rollback plan valid")
    else:
        print(f"runtime disablement rollback plan invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
