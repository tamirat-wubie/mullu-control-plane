#!/usr/bin/env python3
"""Validate capability adapter closure plan schema conformance.

Purpose: keep the adapter source closure plan aligned with its public JSON
schema before aggregate promotion planning consumes it.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: schemas/capability_adapter_closure_plan.schema.json and
.change_assurance/capability_adapter_closure_plan.json.
Invariants:
  - Adapter closure plans match the public protocol schema.
  - Action counts are derived from the action list, not trusted blindly.
  - Every action carries a verification command and receipt validator.
  - Blocker action coverage is complete for non-ready plans.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "capability_adapter_closure_plan.schema.json"
DEFAULT_PLAN = REPO_ROOT / ".change_assurance" / "capability_adapter_closure_plan.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "capability_adapter_closure_plan_schema_validation.json"


@dataclass(frozen=True, slots=True)
class AdapterClosurePlanSchemaValidation:
    """Schema and semantic validation for one adapter closure plan."""

    ok: bool
    errors: tuple[str, ...]
    plan_path: str
    schema_path: str
    action_count: int
    approval_required_action_count: int
    blocker_count: int

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation report."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_capability_adapter_closure_plan_schema(
    *,
    plan_path: Path = DEFAULT_PLAN,
    schema_path: Path = DEFAULT_SCHEMA,
) -> AdapterClosurePlanSchemaValidation:
    """Validate adapter closure plan schema and semantic consistency."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "adapter closure plan schema", errors)
    plan = _load_json_object(plan_path, "adapter closure plan", errors)
    if not schema or not plan:
        return _validation_result(
            plan_path=plan_path,
            schema_path=schema_path,
            errors=errors,
            actions=(),
            blockers=(),
        )

    errors.extend(_validate_schema_instance(schema, plan))
    actions = _actions(plan, errors)
    blockers = _blockers(plan, errors)
    if plan.get("action_count") != len(actions):
        errors.append("action_count does not match actions length")
    if plan.get("source_ready") is True and actions:
        errors.append("source_ready adapter plan must not contain closure actions")
    if plan.get("source_ready") is False and blockers and not actions:
        errors.append("non-ready adapter plan requires closure actions")
    _validate_action_proof_contract(actions, errors)
    _validate_browser_sandbox_receipt_gate(actions, errors)
    _validate_blocker_coverage(blockers=blockers, actions=actions, errors=errors)
    return _validation_result(
        plan_path=plan_path,
        schema_path=schema_path,
        errors=errors,
        actions=actions,
        blockers=blockers,
    )


def write_capability_adapter_closure_plan_schema_validation(
    validation: AdapterClosurePlanSchemaValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic adapter closure plan schema validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_action_proof_contract(
    actions: tuple[dict[str, Any], ...],
    errors: list[str],
) -> None:
    for index, action in enumerate(actions):
        if not str(action.get("verification_command", "")).strip():
            errors.append(f"adapter action {index} missing verification_command")
        if not str(action.get("receipt_validator", "")).strip():
            errors.append(f"adapter action {index} missing receipt_validator")
        if not action.get("evidence_required"):
            errors.append(f"adapter action {index} missing evidence_required")


def _validate_browser_sandbox_receipt_gate(
    actions: tuple[dict[str, Any], ...],
    errors: list[str],
) -> None:
    for index, action in enumerate(actions):
        if action.get("blocker") != "browser_live_evidence_missing":
            continue
        command = str(action.get("command", ""))
        evidence_required = {str(item) for item in action.get("evidence_required", ())}
        required_command_tokens = (
            "produce_browser_sandbox_evidence.py",
            "validate_sandbox_execution_receipt.py",
            "--capability-prefix browser.",
            "--require-no-workspace-changes",
            "validate_browser_sandbox_evidence.py",
            "produce_capability_adapter_live_receipts.py --target browser",
        )
        for token in required_command_tokens:
            if token not in command:
                errors.append(f"browser live action {index} command missing token {token}")
        required_evidence = {
            "browser_sandbox_evidence.json",
            "sandbox_execution_receipt_validation",
            "browser_sandbox_evidence_validation",
            "browser_live_receipt.json",
        }
        missing_evidence = sorted(required_evidence - evidence_required)
        if missing_evidence:
            errors.append(
                f"browser live action {index} evidence_required missing {missing_evidence}"
            )


def _validate_blocker_coverage(
    *,
    blockers: tuple[str, ...],
    actions: tuple[dict[str, Any], ...],
    errors: list[str],
) -> None:
    action_blockers = {str(action.get("blocker", "")) for action in actions}
    uncovered = tuple(blocker for blocker in blockers if blocker not in action_blockers)
    if uncovered:
        errors.append(f"adapter blockers missing closure actions: {list(uncovered)}")


def _validation_result(
    *,
    plan_path: Path,
    schema_path: Path,
    errors: list[str],
    actions: tuple[dict[str, Any], ...],
    blockers: tuple[str, ...],
) -> AdapterClosurePlanSchemaValidation:
    return AdapterClosurePlanSchemaValidation(
        ok=not errors,
        errors=tuple(errors),
        plan_path=str(plan_path),
        schema_path=str(schema_path),
        action_count=len(actions),
        approval_required_action_count=sum(
            1 for action in actions if action.get("approval_required") is True
        ),
        blocker_count=len(blockers),
    )


def _actions(plan: dict[str, Any], errors: list[str]) -> tuple[dict[str, Any], ...]:
    actions = plan.get("actions", ())
    if not isinstance(actions, list):
        errors.append("actions must be a list")
        return ()
    return tuple(action for action in actions if isinstance(action, dict))


def _blockers(plan: dict[str, Any], errors: list[str]) -> tuple[str, ...]:
    blockers = plan.get("blockers", ())
    if not isinstance(blockers, list):
        errors.append("blockers must be a list")
        return ()
    return tuple(str(blocker) for blocker in blockers)


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{label} JSON parse failed: {exc.msg}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse adapter closure plan schema validation arguments."""
    parser = argparse.ArgumentParser(description="Validate adapter closure plan schema.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for adapter closure plan schema validation."""
    args = parse_args(argv)
    validation = validate_capability_adapter_closure_plan_schema(
        plan_path=Path(args.plan),
        schema_path=Path(args.schema),
    )
    write_capability_adapter_closure_plan_schema_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("CAPABILITY ADAPTER CLOSURE PLAN SCHEMA VALID")
    else:
        print(f"CAPABILITY ADAPTER CLOSURE PLAN SCHEMA INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
