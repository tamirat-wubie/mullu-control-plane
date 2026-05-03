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
  - Production readiness is never claimed by this preflight report.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_handoff_preflight.json"
EXPECTED_STEP_NAMES = (
    "operator checklist validation",
    "handoff packet validation",
    "environment binding contract validation",
    "environment binding receipt validation",
    "required environment bindings",
    "closure plan schema validation",
    "closure plan drift validation",
    "promotion readiness report",
)
EXPECTED_READINESS_LEVEL = "pilot-governed-core"


@dataclass(frozen=True, slots=True)
class PromotionHandoffPreflightValidation:
    """Validation result for one handoff preflight report."""

    valid: bool
    ready: bool
    report_path: str
    step_count: int
    blockers: tuple[str, ...]
    missing_environment_variables: tuple[str, ...]
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
    require_ready: bool = False,
) -> PromotionHandoffPreflightValidation:
    """Validate one handoff preflight report."""
    errors: list[str] = []
    report = _load_json_object(report_path, errors)
    if not report:
        return _validation_result(report_path, report, errors)

    steps = report.get("steps", [])
    _validate_scalar_fields(report, errors)
    _validate_steps(steps, errors)
    _validate_derived_fields(report, steps, errors)
    if require_ready and report.get("ready") is not True:
        errors.append("ready must be true")
    return _validation_result(report_path, report, errors)


def _validate_scalar_fields(report: dict[str, Any], errors: list[str]) -> None:
    if report.get("step_count") != len(EXPECTED_STEP_NAMES):
        errors.append(f"step_count must be {len(EXPECTED_STEP_NAMES)}")
    if report.get("readiness_level") != EXPECTED_READINESS_LEVEL:
        errors.append(f"readiness_level must be {EXPECTED_READINESS_LEVEL}")
    if report.get("production_ready") is not False:
        errors.append("production_ready must be false for handoff preflight")
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


def _string_tuple(raw_value: Any, field_name: str, errors: list[str]) -> tuple[str, ...]:
    if not isinstance(raw_value, list):
        errors.append(f"{field_name} must be a list")
        return ()
    if not all(isinstance(item, str) for item in raw_value):
        errors.append(f"{field_name} entries must be strings")
        return ()
    return tuple(raw_value)


def _validation_result(
    report_path: Path,
    report: dict[str, Any],
    errors: list[str],
) -> PromotionHandoffPreflightValidation:
    return PromotionHandoffPreflightValidation(
        valid=not errors,
        ready=report.get("ready") is True,
        report_path=str(report_path),
        step_count=int(report.get("step_count", 0)) if isinstance(report.get("step_count", 0), int) else 0,
        blockers=_string_tuple(report.get("blockers", ()), "blockers", []),
        missing_environment_variables=_string_tuple(
            report.get("missing_environment_variables", ()),
            "missing_environment_variables",
            [],
        ),
        errors=tuple(errors),
    )


def _load_json_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"preflight report could not be read: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"preflight report must be JSON: {exc}")
        return {}
    if not isinstance(parsed, dict):
        errors.append("preflight report root must be an object")
        return {}
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse preflight report validation CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate general-agent promotion handoff preflight report.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for handoff preflight report validation."""
    args = parse_args(argv)
    result = validate_general_agent_promotion_handoff_preflight(
        report_path=Path(args.report),
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
