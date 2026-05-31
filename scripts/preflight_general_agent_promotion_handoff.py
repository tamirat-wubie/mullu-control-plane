#!/usr/bin/env python3
"""Preflight general-agent promotion handoff execution readiness.

Purpose: verify local operator handoff prerequisites before live adapter or
deployment execution begins.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: general-agent promotion checklist, handoff packet, closure plan
schema validation, aggregate drift validation, promotion readiness artifacts, and
environment binding contract.
Invariants:
  - Secret values are never printed or serialized.
  - Preflight does not execute live adapter receipts or deployment publication.
  - Missing environment bindings and validation artifacts remain explicit blockers.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_general_agent_promotion_handoff_packet import (  # noqa: E402
    DEFAULT_PACKET,
    validate_general_agent_promotion_handoff_packet,
)
from scripts.validate_general_agent_promotion_environment_bindings import (  # noqa: E402
    DEFAULT_CONTRACT as DEFAULT_ENVIRONMENT_BINDINGS,
    validate_general_agent_promotion_environment_bindings,
)
from scripts.validate_general_agent_promotion_environment_binding_receipt import (  # noqa: E402
    DEFAULT_RECEIPT as DEFAULT_ENVIRONMENT_BINDING_RECEIPT,
    validate_general_agent_promotion_environment_binding_receipt,
)
from scripts.validate_general_agent_promotion_operator_checklist import (  # noqa: E402
    DEFAULT_CHECKLIST,
    REQUIRED_APPROVAL_BLOCKERS,
    validate_general_agent_promotion_operator_checklist,
)

DEFAULT_SCHEMA_VALIDATION = REPO_ROOT / ".change_assurance" / "general_agent_promotion_closure_plan_schema_validation.json"
DEFAULT_ADAPTER_SCHEMA_VALIDATION = (
    REPO_ROOT / ".change_assurance" / "capability_adapter_closure_plan_schema_validation.json"
)
DEFAULT_DRIFT_VALIDATION = REPO_ROOT / ".change_assurance" / "general_agent_promotion_closure_plan_validation.json"
DEFAULT_READINESS = REPO_ROOT / ".change_assurance" / "general_agent_promotion_readiness.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_handoff_preflight.json"
EXPECTED_APPROVAL_REQUIRED_ACTION_COUNT = 4
EXPECTED_CAPABILITY_COUNT = 75
EXPECTED_CAPSULE_COUNT = 13
EXPECTED_READINESS_LEVEL = "pilot-governed-core"
EXPECTED_SOURCE_PLAN_TYPES = ("adapter", "deployment")
OPTIONAL_SOURCE_PLAN_TYPES = ("portfolio",)

EnvReader = Callable[[str], str | None]


@dataclass(frozen=True, slots=True)
class HandoffPreflightStep:
    """One handoff preflight step."""

    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready step."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EnvironmentBindingAction:
    """Presence-only closure action for one missing environment binding."""

    name: str
    binding_kind: str
    risk: str
    approval_required: bool
    required_for: tuple[str, ...]
    receipt_projection: str
    verification_command: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready action without secret or binding values."""
        return {
            "name": self.name,
            "binding_kind": self.binding_kind,
            "risk": self.risk,
            "approval_required": self.approval_required,
            "required_for": list(self.required_for),
            "receipt_projection": self.receipt_projection,
            "verification_command": self.verification_command,
        }


@dataclass(frozen=True, slots=True)
class HandoffPreflightReport:
    """Full general-agent promotion handoff preflight report."""

    ready: bool
    checked_at: str
    step_count: int
    steps: tuple[HandoffPreflightStep, ...]
    blockers: tuple[str, ...]
    missing_environment_variables: tuple[str, ...]
    environment_binding_actions: tuple[EnvironmentBindingAction, ...]
    readiness_level: str
    production_ready: bool

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready preflight report."""
        return {
            "ready": self.ready,
            "checked_at": self.checked_at,
            "step_count": self.step_count,
            "steps": [step.as_dict() for step in self.steps],
            "blockers": list(self.blockers),
            "missing_environment_variables": list(self.missing_environment_variables),
            "environment_binding_actions": [action.as_dict() for action in self.environment_binding_actions],
            "readiness_level": self.readiness_level,
            "production_ready": self.production_ready,
        }


def preflight_general_agent_promotion_handoff(
    *,
    checklist_path: Path = DEFAULT_CHECKLIST,
    packet_path: Path = DEFAULT_PACKET,
    environment_bindings_path: Path = DEFAULT_ENVIRONMENT_BINDINGS,
    environment_binding_receipt_path: Path = DEFAULT_ENVIRONMENT_BINDING_RECEIPT,
    adapter_schema_validation_path: Path = DEFAULT_ADAPTER_SCHEMA_VALIDATION,
    schema_validation_path: Path = DEFAULT_SCHEMA_VALIDATION,
    drift_validation_path: Path = DEFAULT_DRIFT_VALIDATION,
    readiness_path: Path = DEFAULT_READINESS,
    env_reader: EnvReader | None = None,
) -> HandoffPreflightReport:
    """Preflight the local handoff state without executing live effects."""
    resolved_env_reader = env_reader or os.environ.get
    checklist_result = validate_general_agent_promotion_operator_checklist(checklist_path)
    packet_result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)
    binding_result = validate_general_agent_promotion_environment_bindings(
        contract_path=environment_bindings_path,
        checklist_path=checklist_path,
    )
    binding_receipt_result = validate_general_agent_promotion_environment_binding_receipt(
        receipt_path=environment_binding_receipt_path,
        contract_path=environment_bindings_path,
        require_ready=True,
    )
    environment_step, missing_environment_variables = _required_environment_step(checklist_path, resolved_env_reader)
    environment_binding_actions = _environment_binding_actions(
        environment_bindings_path,
        missing_environment_variables=missing_environment_variables,
    )
    readiness_step, readiness_level, production_ready = _readiness_report_step(readiness_path)
    steps = [
        HandoffPreflightStep(
            name="operator checklist validation",
            passed=checklist_result.valid,
            detail=_validation_detail(checklist_result.errors),
        ),
        HandoffPreflightStep(
            name="handoff packet validation",
            passed=packet_result.valid,
            detail=_validation_detail(packet_result.errors),
        ),
        _conditional_responsibility_debt_step(checklist_path),
        HandoffPreflightStep(
            name="environment binding contract validation",
            passed=binding_result.valid,
            detail=_validation_detail(binding_result.errors),
        ),
        HandoffPreflightStep(
            name="environment binding receipt validation",
            passed=binding_receipt_result.valid,
            detail=_validation_detail(binding_receipt_result.errors),
        ),
        environment_step,
        _adapter_schema_report_step(adapter_schema_validation_path),
        _closure_schema_report_step(schema_validation_path),
        _closure_drift_report_step(
            drift_validation_path,
            schema_validation_path=schema_validation_path,
        ),
        readiness_step,
    ]
    blockers = tuple(step.name for step in steps if not step.passed)
    return HandoffPreflightReport(
        ready=not blockers,
        checked_at=_validation_clock(),
        step_count=len(steps),
        steps=tuple(steps),
        blockers=blockers,
        missing_environment_variables=missing_environment_variables,
        environment_binding_actions=environment_binding_actions,
        readiness_level=readiness_level,
        production_ready=production_ready,
    )


def write_handoff_preflight_report(
    report: HandoffPreflightReport,
    output_path: Path,
) -> Path:
    """Write one handoff preflight report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _required_environment_step(
    checklist_path: Path,
    env_reader: EnvReader,
) -> tuple[HandoffPreflightStep, tuple[str, ...]]:
    payload = _load_json_object(checklist_path)
    required_names = tuple(str(name) for name in payload.get("required_environment_variables", ()))
    missing = tuple(name for name in required_names if not (env_reader(name) or "").strip())
    detail = "all required environment variables are present" if not missing else f"missing={list(missing)}"
    return (
        HandoffPreflightStep(
            name="required environment bindings",
            passed=not missing,
            detail=detail,
        ),
        missing,
    )


def _environment_binding_actions(
    environment_bindings_path: Path,
    *,
    missing_environment_variables: tuple[str, ...],
) -> tuple[EnvironmentBindingAction, ...]:
    contract = _load_json_object(environment_bindings_path)
    bindings = contract.get("bindings", ())
    binding_by_name = {
        str(binding.get("name", "")): binding
        for binding in bindings
        if isinstance(binding, dict) and isinstance(binding.get("name"), str)
    }
    actions: list[EnvironmentBindingAction] = []
    for name in missing_environment_variables:
        binding = binding_by_name.get(name, {})
        required_for = binding.get("required_for", ())
        actions.append(
            EnvironmentBindingAction(
                name=name,
                binding_kind=str(binding.get("binding_kind", "unknown")),
                risk=str(binding.get("risk", "unknown")),
                approval_required=bool(binding.get("approval_required", True)),
                required_for=tuple(str(item) for item in required_for) if isinstance(required_for, list) else (),
                receipt_projection=str(binding.get("receipt_projection", "name_and_presence_only")),
                verification_command=(
                    "Bind the environment variable in the operator runtime without printing or serializing its value, "
                    "then run: python scripts\\emit_general_agent_promotion_environment_binding_receipt.py "
                    "--output .change_assurance\\general_agent_promotion_environment_binding_receipt.json --json "
                    "&& python scripts\\validate_general_agent_promotion_environment_binding_receipt.py "
                    "--receipt .change_assurance\\general_agent_promotion_environment_binding_receipt.json "
                    "--require-ready --json"
                ),
            )
        )
    return tuple(actions)


def _conditional_responsibility_debt_step(checklist_path: Path) -> HandoffPreflightStep:
    payload = _load_json_object(checklist_path)
    observed_values = payload.get(
        "conditional_approval_blockers",
        payload.get("approval_required_blockers", ()),
    )
    observed = {str(item) for item in observed_values} if isinstance(observed_values, list) else set()
    missing = sorted(REQUIRED_APPROVAL_BLOCKERS - observed)
    if missing:
        return HandoffPreflightStep(
            name="conditional responsibility debt blockers",
            passed=False,
            detail=f"conditional responsibility debt blocker drift missing={missing}",
        )
    return HandoffPreflightStep(
        name="conditional responsibility debt blockers",
        passed=True,
        detail="conditional responsibility debt blockers present",
    )


def _adapter_schema_report_step(path: Path) -> HandoffPreflightStep:
    payload, error = _load_report_payload(path)
    if error:
        return HandoffPreflightStep(name="adapter closure schema validation", passed=False, detail=error)
    action_count = payload.get("action_count")
    blocker_count = payload.get("blocker_count")
    passed = (
        payload.get("ok") is True
        and isinstance(action_count, int)
        and action_count > 0
        and isinstance(blocker_count, int)
        and blocker_count > 0
        and payload.get("approval_required_action_count") == 2
    )
    expected_detail = (
        "ok=true "
        f"action_count={action_count} "
        "approval_required_action_count=2 "
        f"blocker_count={blocker_count}"
    )
    detail = expected_detail if passed else f"expected {expected_detail}; observed={_public_report_projection(payload)}"
    return HandoffPreflightStep(name="adapter closure schema validation", passed=passed, detail=detail)


def _closure_schema_report_step(path: Path) -> HandoffPreflightStep:
    payload, error = _load_report_payload(path)
    if error:
        return HandoffPreflightStep(name="closure plan schema validation", passed=False, detail=error)
    action_count = payload.get("action_count")
    source_plan_types = tuple(payload.get("source_plan_types", ()))
    approval_required_count = payload.get("approval_required_action_count")
    passed = (
        payload.get("ok") is True
        and isinstance(action_count, int)
        and action_count > 0
        and isinstance(approval_required_count, int)
        and approval_required_count >= EXPECTED_APPROVAL_REQUIRED_ACTION_COUNT
        and _source_plan_types_allowed(source_plan_types)
    )
    expected_detail = (
        f"ok=true action_count={action_count} "
        f"approval_required_action_count={approval_required_count} "
        f"source_plan_types={list(source_plan_types)}"
    )
    detail = expected_detail if passed else f"expected {expected_detail}; observed={_public_report_projection(payload)}"
    return HandoffPreflightStep(name="closure plan schema validation", passed=passed, detail=detail)


def _closure_drift_report_step(path: Path, *, schema_validation_path: Path) -> HandoffPreflightStep:
    payload, error = _load_report_payload(path)
    if error:
        return HandoffPreflightStep(name="closure plan drift validation", passed=False, detail=error)
    schema_payload, schema_error = _load_report_payload(schema_validation_path)
    if schema_error:
        return HandoffPreflightStep(name="closure plan drift validation", passed=False, detail=schema_error)
    expected_action_count = payload.get("expected_action_count")
    observed_action_count = payload.get("observed_action_count")
    schema_action_count = schema_payload.get("action_count")
    schema_approval_count = schema_payload.get("approval_required_action_count")
    expected_approval_count = payload.get("expected_approval_required_count")
    observed_approval_count = payload.get("observed_approval_required_count")
    passed = (
        payload.get("ok") is True
        and isinstance(expected_action_count, int)
        and expected_action_count > 0
        and schema_action_count == expected_action_count
        and observed_action_count == expected_action_count
        and isinstance(schema_approval_count, int)
        and schema_approval_count >= EXPECTED_APPROVAL_REQUIRED_ACTION_COUNT
        and expected_approval_count == schema_approval_count
        and observed_approval_count == schema_approval_count
    )
    expected_detail = (
        f"ok=true expected_action_count={expected_action_count} "
        f"observed_action_count={observed_action_count} "
        f"expected_approval_required_count={expected_approval_count} "
        f"observed_approval_required_count={observed_approval_count}"
    )
    detail = (
        expected_detail
        if passed
        else (
            "expected ok=true matching schema, drift action, and approval-required counts; "
            f"schema={_public_report_projection(schema_payload)}; "
            f"observed={_public_report_projection(payload)}"
        )
    )
    return HandoffPreflightStep(name="closure plan drift validation", passed=passed, detail=detail)


def _source_plan_types_allowed(source_plan_types: tuple[Any, ...]) -> bool:
    observed = tuple(str(source_plan_type) for source_plan_type in source_plan_types)
    if not set(EXPECTED_SOURCE_PLAN_TYPES).issubset(observed):
        return False
    allowed = set(EXPECTED_SOURCE_PLAN_TYPES).union(OPTIONAL_SOURCE_PLAN_TYPES)
    return all(source_plan_type in allowed for source_plan_type in observed)


def _readiness_report_step(path: Path) -> tuple[HandoffPreflightStep, str, bool]:
    payload, error = _load_report_payload(path)
    if error:
        return (
            HandoffPreflightStep(name="promotion readiness report", passed=False, detail=error),
            "",
            False,
        )
    readiness_level = str(payload.get("readiness_level", ""))
    production_ready = payload.get("ready") is True
    passed = (
        readiness_level == EXPECTED_READINESS_LEVEL
        and payload.get("capability_count") == EXPECTED_CAPABILITY_COUNT
        and payload.get("capsule_count") == EXPECTED_CAPSULE_COUNT
    )
    detail = (
        "readiness_level=pilot-governed-core capability_count=75 capsule_count=13 production_ready=false"
        if passed
        else f"expected pilot-governed-core counts; observed={_public_report_projection(payload)}"
    )
    return (
        HandoffPreflightStep(name="promotion readiness report", passed=passed, detail=detail),
        readiness_level,
        production_ready,
    )


def _load_report_payload(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, f"missing={path}"
    payload = _load_json_object(path)
    if not payload:
        return {}, f"invalid_json_or_empty={path}"
    return payload, ""


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = _loads_strict_json(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _loads_strict_json(raw: str) -> Any:
    return json.loads(raw, parse_constant=_reject_json_constant)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _validation_detail(errors: tuple[str, ...]) -> str:
    return "valid=true" if not errors else f"errors={list(errors)}"


def _public_report_projection(payload: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = (
        "ok",
        "action_count",
        "approval_required_action_count",
        "blocker_count",
        "source_plan_types",
        "expected_action_count",
        "observed_action_count",
        "expected_approval_required_count",
        "observed_approval_required_count",
        "readiness_level",
        "capability_count",
        "capsule_count",
        "ready",
    )
    return {key: payload.get(key) for key in allowed_keys if key in payload}


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse handoff preflight CLI arguments."""
    parser = argparse.ArgumentParser(description="Preflight general-agent promotion handoff readiness.")
    parser.add_argument("--checklist", default=str(DEFAULT_CHECKLIST))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--environment-bindings", default=str(DEFAULT_ENVIRONMENT_BINDINGS))
    parser.add_argument("--environment-binding-receipt", default=str(DEFAULT_ENVIRONMENT_BINDING_RECEIPT))
    parser.add_argument("--adapter-schema-validation", default=str(DEFAULT_ADAPTER_SCHEMA_VALIDATION))
    parser.add_argument("--schema-validation", default=str(DEFAULT_SCHEMA_VALIDATION))
    parser.add_argument("--drift-validation", default=str(DEFAULT_DRIFT_VALIDATION))
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for general-agent promotion handoff preflight."""
    args = parse_args(argv)
    report = preflight_general_agent_promotion_handoff(
        checklist_path=Path(args.checklist),
        packet_path=Path(args.packet),
        environment_bindings_path=Path(args.environment_bindings),
        environment_binding_receipt_path=Path(args.environment_binding_receipt),
        adapter_schema_validation_path=Path(args.adapter_schema_validation),
        schema_validation_path=Path(args.schema_validation),
        drift_validation_path=Path(args.drift_validation),
        readiness_path=Path(args.readiness),
    )
    write_handoff_preflight_report(report, Path(args.output))
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    elif report.ready:
        print("GENERAL AGENT PROMOTION HANDOFF PREFLIGHT READY")
    else:
        print(f"GENERAL AGENT PROMOTION HANDOFF PREFLIGHT BLOCKED blockers={list(report.blockers)}")
    return 0 if report.ready or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
