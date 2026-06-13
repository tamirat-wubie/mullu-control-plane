#!/usr/bin/env python3
"""Validate a general-agent promotion handoff preflight report.

Purpose: keep the handoff preflight receipt machine-checkable before live
adapter receipts or deployment publication are attempted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: .change_assurance/general_agent_promotion_handoff_preflight.json.
Invariants:
  - Preflight step names and step_count match the governed handoff sequence.
  - Report blockers are derived from failed steps.
  - Missing environment variables imply the required environment binding blocker.
  - Missing environment variables emit matching contract-backed presence-only closure actions.
  - Production readiness is evidence-bound by the validated handoff report.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_handoff_preflight.json"
DEFAULT_ENVIRONMENT_BINDINGS = REPO_ROOT / "examples" / "general_agent_promotion_environment_bindings.json"
EXPECTED_STEP_NAMES = (
    "operator checklist validation",
    "handoff packet validation",
    "conditional responsibility debt blockers",
    "environment binding contract validation",
    "environment binding receipt validation",
    "required environment bindings",
    "adapter closure schema validation",
    "closure plan schema validation",
    "closure plan drift validation",
    "promotion readiness report",
)
EXPECTED_READINESS_LEVEL = "production-general-agent"
EXPECTED_PRODUCTION_READY = True


@dataclass(frozen=True, slots=True)
class PromotionHandoffPreflightValidation:
    """Validation result for one handoff preflight report."""

    valid: bool
    ready: bool
    report_path: str
    step_count: int
    blockers: tuple[str, ...]
    missing_environment_variables: tuple[str, ...]
    environment_binding_action_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        payload["missing_environment_variables"] = list(self.missing_environment_variables)
        payload["errors"] = list(self.errors)
        return payload


def validate_general_agent_promotion_handoff_preflight(
    *,
    report_path: Path = DEFAULT_REPORT,
    environment_bindings_path: Path = DEFAULT_ENVIRONMENT_BINDINGS,
    require_ready: bool = False,
) -> PromotionHandoffPreflightValidation:
    """Validate one handoff preflight report."""
    errors: list[str] = []
    report = _load_json_object(report_path, errors)
    if not report:
        return _validation_result(report_path, report, errors)

    steps = report.get("steps", [])
    _validate_scalar_fields(report, errors, require_ready=require_ready)
    _validate_steps(steps, errors)
    _validate_derived_fields(report, steps, errors)
    binding_contract = _load_environment_binding_contract(environment_bindings_path, errors)
    _validate_environment_binding_actions(report, binding_contract, errors)
    if require_ready and report.get("ready") is not True:
        errors.append("ready must be true")
    return _validation_result(report_path, report, errors)


def _validate_scalar_fields(report: dict[str, Any], errors: list[str], *, require_ready: bool) -> None:
    if report.get("step_count") != len(EXPECTED_STEP_NAMES):
        errors.append(f"step_count must be {len(EXPECTED_STEP_NAMES)}")
    readiness_level = report.get("readiness_level")
    production_ready = report.get("production_ready")
    if not isinstance(readiness_level, str) or not readiness_level.strip():
        errors.append("readiness_level must be a non-empty string")
    if not isinstance(production_ready, bool):
        errors.append("production_ready must be a boolean")
    if (report.get("ready") is True or require_ready) and readiness_level != EXPECTED_READINESS_LEVEL:
        errors.append(f"readiness_level must be {EXPECTED_READINESS_LEVEL}")
    if (report.get("ready") is True or require_ready) and production_ready is not EXPECTED_PRODUCTION_READY:
        errors.append(f"production_ready must be {str(EXPECTED_PRODUCTION_READY).lower()} for handoff preflight")
    if not isinstance(report.get("ready"), bool):
        errors.append("ready must be a boolean")


def _validate_steps(steps: Any, errors: list[str]) -> None:
    if not isinstance(steps, list):
        errors.append("steps must be a list")
        return
    observed_names: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            errors.append("steps entries must be objects")
            continue
        observed_names.append(str(step.get("name", "")))
        if not isinstance(step.get("passed"), bool):
            errors.append(f"{step.get('name', 'unnamed')} passed must be a boolean")
        if not isinstance(step.get("detail"), str) or not str(step.get("detail", "")).strip():
            errors.append(f"{step.get('name', 'unnamed')} detail must be a non-empty string")
    if tuple(observed_names) != EXPECTED_STEP_NAMES:
        errors.append(f"steps names must be {list(EXPECTED_STEP_NAMES)}")


def _validate_derived_fields(report: dict[str, Any], steps: Any, errors: list[str]) -> None:
    observed_blockers = _string_tuple(report.get("blockers", ()), "blockers", errors)
    missing_environment_variables = _string_tuple(
        report.get("missing_environment_variables", ()),
        "missing_environment_variables",
        errors,
    )
    if not isinstance(steps, list):
        return
    expected_blockers = tuple(
        str(step.get("name", ""))
        for step in steps
        if isinstance(step, dict) and step.get("passed") is not True
    )
    if observed_blockers != expected_blockers:
        errors.append(f"blockers must match failed steps: expected={list(expected_blockers)}")
    expected_ready = not expected_blockers
    if report.get("ready") is not expected_ready:
        errors.append(f"ready must be {expected_ready} based on blockers")
    if missing_environment_variables and "required environment bindings" not in observed_blockers:
        errors.append("missing_environment_variables require required environment bindings blocker")


def _validate_environment_binding_actions(
    report: dict[str, Any],
    binding_contract: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    missing_environment_variables = _string_tuple(
        report.get("missing_environment_variables", ()),
        "missing_environment_variables",
        errors,
    )
    raw_actions = report.get("environment_binding_actions")
    if not isinstance(raw_actions, list):
        errors.append("environment_binding_actions must be a list")
        return
    observed_names: list[str] = []
    for action in raw_actions:
        if not isinstance(action, dict):
            errors.append("environment_binding_actions entries must be objects")
            continue
        _validate_environment_binding_action(action, binding_contract, errors)
        observed_names.append(str(action.get("name", "")))
    _validate_no_duplicate_strings(observed_names, "environment_binding_actions names", errors)
    if tuple(observed_names) != missing_environment_variables:
        errors.append(
            "environment_binding_actions names must match missing_environment_variables: "
            f"expected={list(missing_environment_variables)}"
        )
    if not missing_environment_variables and raw_actions:
        errors.append("environment_binding_actions must be empty when no environment variables are missing")


def _validate_environment_binding_action(
    action: dict[str, Any],
    binding_contract: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    required_fields = (
        "name",
        "binding_kind",
        "risk",
        "approval_required",
        "required_for",
        "receipt_projection",
        "verification_command",
    )
    for field_name in required_fields:
        if field_name not in action:
            errors.append(f"environment binding action missing {field_name}")
    if not isinstance(action.get("name"), str) or not action.get("name", "").strip():
        errors.append("environment binding action name must be a non-empty string")
    name = str(action.get("name", ""))
    if action.get("binding_kind") not in {"artifact_path", "audio_path", "url", "secret"}:
        errors.append(f"{name or 'unnamed'} binding_kind is invalid")
    if action.get("risk") not in {"medium", "high", "critical"}:
        errors.append(f"{name or 'unnamed'} risk is invalid")
    if not isinstance(action.get("approval_required"), bool):
        errors.append(f"{name or 'unnamed'} approval_required must be a boolean")
    required_for = action.get("required_for")
    if not isinstance(required_for, list) or not required_for or not all(isinstance(item, str) for item in required_for):
        errors.append(f"{name or 'unnamed'} required_for must be a non-empty string list")
    if action.get("receipt_projection") != "name_and_presence_only":
        errors.append(f"{name or 'unnamed'} receipt_projection must be name_and_presence_only")
    _validate_environment_binding_contract_match(action, binding_contract, errors)
    verification_command = action.get("verification_command")
    if not isinstance(verification_command, str) or not verification_command.strip():
        errors.append(f"{name or 'unnamed'} verification_command must be a non-empty string")
        return
    if "without printing or serializing" not in verification_command:
        errors.append(f"{name or 'unnamed'} verification_command must forbid value serialization")
    if "emit_general_agent_promotion_environment_binding_receipt.py" not in verification_command:
        errors.append(f"{name or 'unnamed'} verification_command must emit binding receipt")
    if "validate_general_agent_promotion_environment_binding_receipt.py" not in verification_command:
        errors.append(f"{name or 'unnamed'} verification_command must validate binding receipt")
    if " --require-ready" not in verification_command:
        errors.append(f"{name or 'unnamed'} verification_command must require ready receipt")
    if any(forbidden in action for forbidden in ("value", "secret_value", "token", "credential")):
        errors.append(f"{name or 'unnamed'} action must not carry serialized values")


def _validate_environment_binding_contract_match(
    action: dict[str, Any],
    binding_contract: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    name = str(action.get("name", ""))
    if not name:
        return
    expected = binding_contract.get(name)
    if expected is None:
        errors.append(f"{name} action is not declared in environment binding contract")
        return
    for field_name in ("binding_kind", "risk", "approval_required", "receipt_projection"):
        if action.get(field_name) != expected.get(field_name):
            errors.append(f"{name} {field_name} must match environment binding contract")
    expected_required_for = expected.get("required_for", ())
    observed_required_for = action.get("required_for", ())
    if (
        not isinstance(expected_required_for, list)
        or not isinstance(observed_required_for, list)
        or tuple(observed_required_for) != tuple(expected_required_for)
    ):
        errors.append(f"{name} required_for must match environment binding contract")


def _string_tuple(raw_value: Any, field_name: str, errors: list[str]) -> tuple[str, ...]:
    if not isinstance(raw_value, list):
        errors.append(f"{field_name} must be a list")
        return ()
    if not all(isinstance(item, str) for item in raw_value):
        errors.append(f"{field_name} entries must be strings")
        return ()
    _validate_no_duplicate_strings(raw_value, field_name, errors)
    return tuple(raw_value)


def _validate_no_duplicate_strings(values: list[str], field_name: str, errors: list[str]) -> None:
    observed: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in observed and value not in duplicates:
            duplicates.append(value)
        observed.add(value)
    if duplicates:
        errors.append(f"{field_name} entries must be unique: duplicates={duplicates}")


def _load_environment_binding_contract(
    environment_bindings_path: Path,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    try:
        parsed = _loads_strict_json(environment_bindings_path.read_text(encoding="utf-8"))
    except OSError:
        errors.append("environment binding contract could not be read")
        return {}
    except (json.JSONDecodeError, ValueError):
        errors.append("environment binding contract must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append("environment binding contract root must be an object")
        return {}
    bindings = parsed.get("bindings", ())
    if not isinstance(bindings, list):
        errors.append("environment binding contract bindings must be a list")
        return {}
    return {
        str(binding.get("name", "")): binding
        for binding in bindings
        if isinstance(binding, dict) and isinstance(binding.get("name"), str)
    }


def _validation_result(
    report_path: Path,
    report: dict[str, Any],
    errors: list[str],
) -> PromotionHandoffPreflightValidation:
    public_report_path = str(report_path) if report else "<unavailable>"
    return PromotionHandoffPreflightValidation(
        valid=not errors,
        ready=report.get("ready") is True,
        report_path=public_report_path,
        step_count=int(report.get("step_count", 0)) if isinstance(report.get("step_count", 0), int) else 0,
        blockers=_string_tuple(report.get("blockers", ()), "blockers", []),
        missing_environment_variables=_string_tuple(
            report.get("missing_environment_variables", ()),
            "missing_environment_variables",
            [],
        ),
        environment_binding_action_count=(
            len(report.get("environment_binding_actions", ()))
            if isinstance(report.get("environment_binding_actions"), list)
            else 0
        ),
        errors=tuple(errors),
    )


def _load_json_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = _loads_strict_json(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append("preflight report could not be read")
        return {}
    except (json.JSONDecodeError, ValueError):
        errors.append("preflight report must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append("preflight report root must be an object")
        return {}
    return parsed


def _loads_strict_json(raw: str) -> Any:
    return json.loads(raw, parse_constant=_reject_json_constant)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse preflight report validation CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate general-agent promotion handoff preflight report.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--environment-bindings", default=str(DEFAULT_ENVIRONMENT_BINDINGS))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for handoff preflight report validation."""
    args = parse_args(argv)
    result = validate_general_agent_promotion_handoff_preflight(
        report_path=Path(args.report),
        environment_bindings_path=Path(args.environment_bindings),
        require_ready=args.require_ready,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"general-agent promotion handoff preflight report ok ready={result.ready}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
