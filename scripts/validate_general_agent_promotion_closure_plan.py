#!/usr/bin/env python3
"""Validate full general-agent promotion closure plan consistency.

Purpose: prove the aggregate closure plan faithfully reflects readiness,
adapter closure, and deployment closure source plans.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: .change_assurance/general_agent_promotion_closure_plan.json,
adapter closure plan, deployment publication closure plan, and promotion readiness.
Invariants:
  - Every source action appears exactly once in the aggregate plan.
  - Adapter closure actions preserve verification commands and receipt validators.
  - Approval counts are derived from action payloads, not trusted blindly.
  - Source readiness and readiness level match the readiness artifact.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_READINESS = REPO_ROOT / ".change_assurance" / "general_agent_promotion_readiness.json"
DEFAULT_ADAPTER_PLAN = REPO_ROOT / ".change_assurance" / "capability_adapter_closure_plan.json"
DEFAULT_DEPLOYMENT_PLAN = REPO_ROOT / ".change_assurance" / "deployment_publication_closure_plan.json"
DEFAULT_PROMOTION_PLAN = REPO_ROOT / ".change_assurance" / "general_agent_promotion_closure_plan.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_closure_plan_validation.json"


@dataclass(frozen=True, slots=True)
class ClosurePlanValidation:
    """Validation result for one aggregate promotion closure plan."""

    ok: bool
    errors: tuple[str, ...]
    plan_path: str
    expected_action_count: int
    observed_action_count: int
    expected_approval_required_count: int
    observed_approval_required_count: int

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation report."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_general_agent_promotion_closure_plan(
    *,
    promotion_plan_path: Path = DEFAULT_PROMOTION_PLAN,
    readiness_path: Path = DEFAULT_READINESS,
    adapter_plan_path: Path = DEFAULT_ADAPTER_PLAN,
    deployment_plan_path: Path = DEFAULT_DEPLOYMENT_PLAN,
) -> ClosurePlanValidation:
    """Validate aggregate promotion closure plan consistency."""
    errors: list[str] = []
    promotion_plan = _load_json_object(promotion_plan_path, "promotion closure plan", errors)
    readiness = _load_json_object(readiness_path, "promotion readiness", errors)
    adapter_plan = _load_json_object(adapter_plan_path, "adapter closure plan", errors)
    deployment_plan = _load_json_object(deployment_plan_path, "deployment publication closure plan", errors)
    if not all((promotion_plan, readiness, adapter_plan, deployment_plan)):
        return _validation_result(
            promotion_plan_path=promotion_plan_path,
            errors=errors,
            expected_actions=(),
            observed_actions=(),
        )

    expected_actions = (
        *_source_actions(adapter_plan, source_plan_type="adapter", errors=errors),
        *_source_actions(deployment_plan, source_plan_type="deployment", errors=errors),
    )
    observed_actions = _observed_actions(promotion_plan, errors)
    _validate_scalar_fields(
        promotion_plan=promotion_plan,
        readiness=readiness,
        expected_actions=expected_actions,
        observed_actions=observed_actions,
        errors=errors,
    )
    _validate_action_identity(
        expected_actions=expected_actions,
        observed_actions=observed_actions,
        errors=errors,
    )
    _validate_adapter_action_proof_contract(
        expected_actions=expected_actions,
        observed_actions=observed_actions,
        errors=errors,
    )
    _validate_action_proof_fields(
        expected_actions=expected_actions,
        observed_actions=observed_actions,
        errors=errors,
    )
    return _validation_result(
        promotion_plan_path=promotion_plan_path,
        errors=errors,
        expected_actions=expected_actions,
        observed_actions=observed_actions,
    )


def write_general_agent_promotion_closure_plan_validation(
    validation: ClosurePlanValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic closure plan validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_scalar_fields(
    *,
    promotion_plan: dict[str, Any],
    readiness: dict[str, Any],
    expected_actions: tuple[dict[str, Any], ...],
    observed_actions: tuple[dict[str, Any], ...],
    errors: list[str],
) -> None:
    expected_approvals = _approval_count(expected_actions)
    observed_approvals = _approval_count(observed_actions)
    if promotion_plan.get("source_ready") is not (readiness.get("ready") is True):
        errors.append("source_ready does not match promotion readiness ready field")
    if promotion_plan.get("readiness_level") != readiness.get("readiness_level"):
        errors.append("readiness_level does not match promotion readiness artifact")
    if promotion_plan.get("total_action_count") != len(observed_actions):
        errors.append("total_action_count does not match observed actions")
    if promotion_plan.get("total_action_count") != len(expected_actions):
        errors.append("total_action_count does not match source plan actions")
    if promotion_plan.get("approval_required_action_count") != observed_approvals:
        errors.append("approval_required_action_count does not match observed actions")
    if promotion_plan.get("approval_required_action_count") != expected_approvals:
        errors.append("approval_required_action_count does not match source plan actions")


def _validate_action_identity(
    *,
    expected_actions: tuple[dict[str, Any], ...],
    observed_actions: tuple[dict[str, Any], ...],
    errors: list[str],
) -> None:
    expected_keys = [_action_key(action) for action in expected_actions]
    observed_keys = [_action_key(action) for action in observed_actions]
    missing = tuple(key for key in expected_keys if key not in observed_keys)
    unexpected = tuple(key for key in observed_keys if key not in expected_keys)
    duplicate_observed = tuple(
        key for key in dict.fromkeys(observed_keys) if observed_keys.count(key) > 1
    )
    if missing:
        errors.append(f"aggregate plan missing source actions: {list(missing)}")
    if unexpected:
        errors.append(f"aggregate plan has unexpected actions: {list(unexpected)}")
    if duplicate_observed:
        errors.append(f"aggregate plan has duplicate actions: {list(duplicate_observed)}")


def _validate_adapter_action_proof_contract(
    *,
    expected_actions: tuple[dict[str, Any], ...],
    observed_actions: tuple[dict[str, Any], ...],
    errors: list[str],
) -> None:
    observed_by_key = {_action_key(action): action for action in observed_actions}
    for expected in expected_actions:
        if expected.get("source_plan_type") != "adapter":
            continue
        key = _action_key(expected)
        observed = observed_by_key.get(key)
        for field_name in ("verification_command", "receipt_validator"):
            expected_value = str(expected.get(field_name, "")).strip()
            if not expected_value:
                errors.append(f"adapter proof field drift: source action {key} missing {field_name}")
                continue
            if observed is None:
                continue
            observed_value = str(observed.get(field_name, "")).strip()
            if not observed_value:
                errors.append(f"adapter proof field drift: aggregate action {key} missing {field_name}")
            elif observed_value != expected_value:
                errors.append(f"adapter proof field drift: aggregate action {key} changed {field_name}")


def _validate_action_proof_fields(
    *,
    expected_actions: tuple[dict[str, Any], ...],
    observed_actions: tuple[dict[str, Any], ...],
    errors: list[str],
) -> None:
    observed_by_key = {_action_key(action): action for action in observed_actions}
    for expected_action in expected_actions:
        key = _action_key(expected_action)
        observed_action = observed_by_key.get(key)
        if observed_action is None:
            continue
        for field_name in ("verification_command", "receipt_validator"):
            expected_value = expected_action.get(field_name)
            if expected_value is None:
                continue
            if observed_action.get(field_name) != expected_value:
                errors.append(
                    "aggregate plan proof field drift: "
                    f"action={list(key)} field={field_name}"
                )


def _source_actions(
    plan: dict[str, Any],
    *,
    source_plan_type: str,
    errors: list[str],
) -> tuple[dict[str, Any], ...]:
    actions = plan.get("actions", ())
    if not isinstance(actions, list):
        errors.append(f"{source_plan_type} source plan actions must be a list")
        return ()
    tagged: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            errors.append(f"{source_plan_type} source action {index} must be an object")
            continue
        tagged_action = dict(action)
        tagged_action["source_plan_type"] = source_plan_type
        tagged.append(tagged_action)
    return tuple(tagged)


def _observed_actions(
    promotion_plan: dict[str, Any],
    errors: list[str],
) -> tuple[dict[str, Any], ...]:
    actions = promotion_plan.get("actions", ())
    if not isinstance(actions, list):
        errors.append("promotion closure plan actions must be a list")
        return ()
    observed: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            errors.append(f"promotion closure action {index} must be an object")
            continue
        source_plan_type = action.get("source_plan_type")
        if source_plan_type not in {"adapter", "deployment"}:
            errors.append(f"promotion closure action {index} has invalid source_plan_type")
        observed.append(action)
    return tuple(observed)


def _action_key(action: dict[str, Any]) -> tuple[str, str]:
    return (str(action.get("source_plan_type", "")), str(action.get("action_id", "")))


def _approval_count(actions: tuple[dict[str, Any], ...]) -> int:
    return sum(1 for action in actions if action.get("approval_required") is True)


def _validation_result(
    *,
    promotion_plan_path: Path,
    errors: list[str],
    expected_actions: tuple[dict[str, Any], ...],
    observed_actions: tuple[dict[str, Any], ...],
) -> ClosurePlanValidation:
    return ClosurePlanValidation(
        ok=not errors,
        errors=tuple(errors),
        plan_path=str(promotion_plan_path),
        expected_action_count=len(expected_actions),
        observed_action_count=len(observed_actions),
        expected_approval_required_count=_approval_count(expected_actions),
        observed_approval_required_count=_approval_count(observed_actions),
    )


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
    """Parse aggregate closure plan validation arguments."""
    parser = argparse.ArgumentParser(description="Validate full promotion closure plan consistency.")
    parser.add_argument("--plan", default=str(DEFAULT_PROMOTION_PLAN))
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--adapter-plan", default=str(DEFAULT_ADAPTER_PLAN))
    parser.add_argument("--deployment-plan", default=str(DEFAULT_DEPLOYMENT_PLAN))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for aggregate closure plan validation."""
    args = parse_args(argv)
    validation = validate_general_agent_promotion_closure_plan(
        promotion_plan_path=Path(args.plan),
        readiness_path=Path(args.readiness),
        adapter_plan_path=Path(args.adapter_plan),
        deployment_plan_path=Path(args.deployment_plan),
    )
    write_general_agent_promotion_closure_plan_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("GENERAL AGENT PROMOTION CLOSURE PLAN VALID")
    else:
        print(f"GENERAL AGENT PROMOTION CLOSURE PLAN INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
