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
    validate_general_agent_promotion_operator_checklist,
)

DEFAULT_SCHEMA_VALIDATION = REPO_ROOT / ".change_assurance" / "general_agent_promotion_closure_plan_schema_validation.json"
DEFAULT_DRIFT_VALIDATION = REPO_ROOT / ".change_assurance" / "general_agent_promotion_closure_plan_validation.json"
DEFAULT_READINESS = REPO_ROOT / ".change_assurance" / "general_agent_promotion_readiness.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_handoff_preflight.json"
EXPECTED_ACTION_COUNT = 14
EXPECTED_APPROVAL_REQUIRED_ACTION_COUNT = 4
EXPECTED_CAPABILITY_COUNT = 52
EXPECTED_CAPSULE_COUNT = 10
EXPECTED_READINESS_LEVEL = "pilot-governed-core"
EXPECTED_SOURCE_PLAN_TYPES = ("adapter", "deployment")

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
class HandoffPreflightReport:
    """Full general-agent promotion handoff preflight report."""

    ready: bool
    checked_at: str
    step_count: int
    steps: tuple[HandoffPreflightStep, ...]
    blockers: tuple[str, ...]
    missing_environment_variables: tuple[str, ...]
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
            "readiness_level": self.readiness_level,
            "production_ready": self.production_ready,
        }


def preflight_general_agent_promotion_handoff(
    *,
    checklist_path: Path = DEFAULT_CHECKLIST,
    packet_path: Path = DEFAULT_PACKET,
    environment_bindings_path: Path = DEFAULT_ENVIRONMENT_BINDINGS,
    environment_binding_receipt_path: Path = DEFAULT_ENVIRONMENT_BINDING_RECEIPT,
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
        _closure_schema_report_step(schema_validation_path),
        _closure_drift_report_step(drift_validation_path),
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


def _closure_schema_report_step(path: Path) -> HandoffPreflightStep:
    payload, error = _load_report_payload(path)
    if error:
        return HandoffPreflightStep(name="closure plan schema validation", passed=False, detail=error)
    passed = (
        payload.get("ok") is True
        and payload.get("action_count") == EXPECTED_ACTION_COUNT
        and payload.get("approval_required_action_count") == EXPECTED_APPROVAL_REQUIRED_ACTION_COUNT
        and tuple(payload.get("source_plan_types", ())) == EXPECTED_SOURCE_PLAN_TYPES
    )
    detail = (
        "ok=true action_count=14 approval_required_action_count=4 source_plan_types=['adapter', 'deployment']"
        if passed
        else (
            "expected ok=true action_count=14 approval_required_action_count=4 "
            f"source_plan_types=['adapter', 'deployment']; observed={_public_report_projection(payload)}"
        )
    )
    return HandoffPreflightStep(name="closure plan schema validation", passed=passed, detail=detail)


def _closure_drift_report_step(path: Path) -> HandoffPreflightStep:
    payload, error = _load_report_payload(path)
    if error:
        return HandoffPreflightStep(name="closure plan drift validation", passed=False, detail=error)
    passed = (
        payload.get("ok") is True
        and payload.get("expected_action_count") == EXPECTED_ACTION_COUNT
        and payload.get("observed_action_count") == EXPECTED_ACTION_COUNT
        and payload.get("expected_approval_required_count") == EXPECTED_APPROVAL_REQUIRED_ACTION_COUNT
        and payload.get("observed_approval_required_count") == EXPECTED_APPROVAL_REQUIRED_ACTION_COUNT
    )
    detail = (
        "ok=true expected_action_count=14 observed_action_count=14 expected_approval_required_count=4 observed_approval_required_count=4"
        if passed
        else (
            "expected ok=true matching action and approval-required counts; "
            f"observed={_public_report_projection(payload)}"
        )
    )
    return HandoffPreflightStep(name="closure plan drift validation", passed=passed, detail=detail)


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
        "readiness_level=pilot-governed-core capability_count=52 capsule_count=10 production_ready=false"
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
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _validation_detail(errors: tuple[str, ...]) -> str:
    return "valid=true" if not errors else f"errors={list(errors)}"


def _public_report_projection(payload: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = (
        "ok",
        "action_count",
        "approval_required_action_count",
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
