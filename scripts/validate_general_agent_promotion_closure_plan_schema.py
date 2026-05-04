#!/usr/bin/env python3
"""Validate aggregate promotion closure plan schema conformance.

Purpose: keep the operator-facing general-agent promotion closure plan aligned
with its public JSON schema before any approval or execution step.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: schemas/general_agent_promotion_closure_plan.schema.json and
.change_assurance/general_agent_promotion_closure_plan.json.
Invariants:
  - The aggregate closure plan matches the public protocol schema.
  - Adapter closure actions carry verification commands and receipt validators.
  - Action counts are derived from the action list, not trusted blindly.
  - Approval-required counts are recomputed from action payloads.
  - Non-empty plans must contain adapter and deployment source actions.
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

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "general_agent_promotion_closure_plan.schema.json"
DEFAULT_PLAN = REPO_ROOT / ".change_assurance" / "general_agent_promotion_closure_plan.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_closure_plan_schema_validation.json"


@dataclass(frozen=True, slots=True)
class PromotionClosurePlanSchemaValidation:
    """Schema and semantic count validation for one aggregate closure plan."""

    ok: bool
    errors: tuple[str, ...]
    plan_path: str
    schema_path: str
    action_count: int
    approval_required_action_count: int
    source_plan_types: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation report."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["source_plan_types"] = list(self.source_plan_types)
        return payload


def validate_general_agent_promotion_closure_plan_schema(
    *,
    plan_path: Path = DEFAULT_PLAN,
    schema_path: Path = DEFAULT_SCHEMA,
) -> PromotionClosurePlanSchemaValidation:
    """Validate aggregate promotion closure plan schema and count consistency."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "closure plan schema", errors)
    plan = _load_json_object(plan_path, "promotion closure plan", errors)
    if not schema or not plan:
        return _validation_result(
            plan_path=plan_path,
            schema_path=schema_path,
            errors=errors,
            actions=(),
        )

    errors.extend(_validate_schema_instance(schema, plan))
    actions = _actions(plan, errors)
    action_count = len(actions)
    approval_required_count = sum(1 for action in actions if action.get("approval_required") is True)
    source_plan_types = tuple(sorted({str(action.get("source_plan_type", "")) for action in actions}))

    if plan.get("total_action_count") != action_count:
        errors.append("total_action_count does not match actions length")
    if plan.get("approval_required_action_count") != approval_required_count:
        errors.append("approval_required_action_count does not match actions")
    if approval_required_count > action_count:
        errors.append("approval_required_action_count cannot exceed total_action_count")
    if action_count and {"adapter", "deployment"} - set(source_plan_types):
        errors.append("non-empty promotion closure plan must include adapter and deployment source actions")
    for index, action in enumerate(actions):
        if action.get("source_plan_type") != "adapter":
            continue
        if not str(action.get("verification_command", "")).strip():
            errors.append(f"adapter action {index} missing verification_command")
        if not str(action.get("receipt_validator", "")).strip():
            errors.append(f"adapter action {index} missing receipt_validator")

    return _validation_result(
        plan_path=plan_path,
        schema_path=schema_path,
        errors=errors,
        actions=actions,
    )


def write_general_agent_promotion_closure_plan_schema_validation(
    validation: PromotionClosurePlanSchemaValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic schema validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validation_result(
    *,
    plan_path: Path,
    schema_path: Path,
    errors: list[str],
    actions: tuple[dict[str, Any], ...],
) -> PromotionClosurePlanSchemaValidation:
    source_plan_types = tuple(sorted({str(action.get("source_plan_type", "")) for action in actions}))
    return PromotionClosurePlanSchemaValidation(
        ok=not errors,
        errors=tuple(errors),
        plan_path=str(plan_path),
        schema_path=str(schema_path),
        action_count=len(actions),
        approval_required_action_count=sum(1 for action in actions if action.get("approval_required") is True),
        source_plan_types=source_plan_types,
    )


def _actions(plan: dict[str, Any], errors: list[str]) -> tuple[dict[str, Any], ...]:
    actions = plan.get("actions", ())
    if not isinstance(actions, list):
        errors.append("actions must be a list")
        return ()
    return tuple(action for action in actions if isinstance(action, dict))


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
    """Parse aggregate closure plan schema validation arguments."""
    parser = argparse.ArgumentParser(description="Validate aggregate promotion closure plan schema.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for aggregate closure plan schema validation."""
    args = parse_args(argv)
    validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=Path(args.plan),
        schema_path=Path(args.schema),
    )
    write_general_agent_promotion_closure_plan_schema_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("GENERAL AGENT PROMOTION CLOSURE PLAN SCHEMA VALID")
    else:
        print(f"GENERAL AGENT PROMOTION CLOSURE PLAN SCHEMA INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
