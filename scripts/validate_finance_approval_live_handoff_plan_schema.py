#!/usr/bin/env python3
"""Validate finance approval live handoff plan schema conformance.

Purpose: keep the finance live email handoff plan aligned with its public JSON
schema before operators use it for readiness promotion.
Governance scope: finance handoff blockers, email/calendar credential binding,
read-only receipt closure, and proof-contract validation.
Dependencies: schemas/finance_approval_live_handoff_plan.schema.json and
.change_assurance/finance_approval_live_handoff_plan.json.
Invariants:
  - The plan matches the public protocol schema.
  - Action counts are derived from the action list.
  - Only finance-relevant email/calendar blockers are permitted.
  - Credential actions require approval and scope evidence.
  - Live receipt actions require a read-only email/calendar probe.
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

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "finance_approval_live_handoff_plan.schema.json"
DEFAULT_PLAN = REPO_ROOT / ".change_assurance" / "finance_approval_live_handoff_plan.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_live_handoff_plan_schema_validation.json"
ALLOWED_BLOCKERS = frozenset(
    {
        "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN",
        "email_calendar_live_evidence_missing",
        "email_calendar_evidence_not_closed",
    }
)


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffPlanSchemaValidation:
    """Schema and semantic validation for one finance live handoff plan."""

    ok: bool
    errors: tuple[str, ...]
    plan_path: str
    schema_path: str
    action_count: int
    approval_required_action_count: int
    blocker_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_finance_approval_live_handoff_plan_schema(
    *,
    plan_path: Path = DEFAULT_PLAN,
    schema_path: Path = DEFAULT_SCHEMA,
) -> FinanceLiveHandoffPlanSchemaValidation:
    """Validate finance live handoff plan schema and semantic consistency."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "finance live handoff plan schema", errors)
    plan = _load_json_object(plan_path, "finance live handoff plan", errors)
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
    if plan.get("ready") is True and (actions or blockers):
        errors.append("ready finance handoff plan must not contain blockers or actions")
    if plan.get("ready") is False and blockers and not actions:
        errors.append("non-ready finance handoff plan requires closure actions")
    _validate_finance_blocker_scope(blockers, errors)
    _validate_action_proof_contract(actions, errors)
    _validate_blocker_coverage(blockers=blockers, actions=actions, errors=errors)
    _validate_email_calendar_credential_action(actions, errors)
    _validate_email_calendar_live_receipt_action(actions, errors)
    return _validation_result(
        plan_path=plan_path,
        schema_path=schema_path,
        errors=errors,
        actions=actions,
        blockers=blockers,
    )


def write_finance_live_handoff_plan_schema_validation(
    validation: FinanceLiveHandoffPlanSchemaValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic finance handoff plan schema validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_finance_blocker_scope(blockers: tuple[str, ...], errors: list[str]) -> None:
    out_of_scope = tuple(blocker for blocker in blockers if blocker not in ALLOWED_BLOCKERS)
    if out_of_scope:
        errors.append(f"finance handoff blockers out of scope: {list(out_of_scope)}")


def _validate_action_proof_contract(actions: tuple[dict[str, Any], ...], errors: list[str]) -> None:
    for index, action in enumerate(actions):
        if not str(action.get("verification_command", "")).strip():
            errors.append(f"finance handoff action {index} missing verification_command")
        if not str(action.get("receipt_validator", "")).strip():
            errors.append(f"finance handoff action {index} missing receipt_validator")
        if not action.get("evidence_required"):
            errors.append(f"finance handoff action {index} missing evidence_required")


def _validate_blocker_coverage(
    *,
    blockers: tuple[str, ...],
    actions: tuple[dict[str, Any], ...],
    errors: list[str],
) -> None:
    action_blockers = {str(action.get("blocker", "")) for action in actions}
    uncovered = tuple(blocker for blocker in blockers if blocker not in action_blockers)
    if uncovered:
        errors.append(f"finance handoff blockers missing closure actions: {list(uncovered)}")


def _validate_email_calendar_credential_action(actions: tuple[dict[str, Any], ...], errors: list[str]) -> None:
    for index, action in enumerate(actions):
        if action.get("blocker") != "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN":
            continue
        evidence_required = {str(item) for item in action.get("evidence_required", ())}
        if action.get("action_type") != "credential":
            errors.append(f"email/calendar credential action {index} must use action_type=credential")
        if action.get("approval_required") is not True:
            errors.append(f"email/calendar credential action {index} must require approval")
        verification_command = str(action.get("verification_command", ""))
        required_verification_tokens = (
            "validate_finance_approval_email_calendar_binding_receipt.py",
            "--require-ready",
            "collect_capability_adapter_evidence.py",
        )
        for token in required_verification_tokens:
            if token not in verification_command:
                errors.append(f"email/calendar credential action {index} verification_command missing token {token}")
        missing_evidence = sorted({"connector_scope_attestation", "secret_presence_attestation"} - evidence_required)
        if "finance_approval_email_calendar_binding_receipt.json" not in evidence_required:
            errors.append(
                f"email/calendar credential action {index} evidence_required missing "
                "finance_approval_email_calendar_binding_receipt.json"
            )
        if missing_evidence:
            errors.append(f"email/calendar credential action {index} evidence_required missing {missing_evidence}")


def _validate_email_calendar_live_receipt_action(actions: tuple[dict[str, Any], ...], errors: list[str]) -> None:
    for index, action in enumerate(actions):
        if action.get("blocker") != "email_calendar_live_evidence_missing":
            continue
        command = str(action.get("command", ""))
        evidence_required = {str(item) for item in action.get("evidence_required", ())}
        required_tokens = (
            "produce_capability_adapter_live_receipts.py",
            "--target email-calendar",
            "--strict",
        )
        for token in required_tokens:
            if token not in command:
                errors.append(f"email/calendar live action {index} command missing token {token}")
        missing_evidence = sorted({"email_calendar_live_receipt.json", "read_only_probe_receipt"} - evidence_required)
        if missing_evidence:
            errors.append(f"email/calendar live action {index} evidence_required missing {missing_evidence}")


def _validation_result(
    *,
    plan_path: Path,
    schema_path: Path,
    errors: list[str],
    actions: tuple[dict[str, Any], ...],
    blockers: tuple[str, ...],
) -> FinanceLiveHandoffPlanSchemaValidation:
    return FinanceLiveHandoffPlanSchemaValidation(
        ok=not errors,
        errors=tuple(errors),
        plan_path=str(plan_path),
        schema_path=str(schema_path),
        action_count=len(actions),
        approval_required_action_count=sum(1 for action in actions if action.get("approval_required") is True),
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
    except json.JSONDecodeError:
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance handoff plan schema validation arguments."""
    parser = argparse.ArgumentParser(description="Validate finance approval live handoff plan schema.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance handoff plan schema validation."""
    args = parse_args(argv)
    validation = validate_finance_approval_live_handoff_plan_schema(
        plan_path=Path(args.plan),
        schema_path=Path(args.schema),
    )
    write_finance_live_handoff_plan_schema_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("FINANCE LIVE HANDOFF PLAN SCHEMA VALID")
    else:
        print(f"FINANCE LIVE HANDOFF PLAN SCHEMA INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
