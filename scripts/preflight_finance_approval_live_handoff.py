#!/usr/bin/env python3
"""Preflight finance approval live email handoff readiness.

Purpose: verify local finance handoff artifacts before any live email/calendar
receipt or production promotion command is executed.
Governance scope: finance pilot readiness, handoff plan schema validation,
redacted connector binding receipt validation, closure-run validation, and
explicit blocker reporting.
Dependencies: finance live handoff plan validation, finance connector binding
receipt validation, finance closure-run validation, and finance approval pilot
readiness validation.
Invariants:
  - Preflight never executes live adapter receipts.
  - Secret values are never read beyond presence receipts.
  - Binding receipt readiness is required before live handoff readiness.
  - Closure run schema validity is required before live handoff readiness.
  - Blocked states remain explicit and machine-readable.
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

from scripts.validate_finance_approval_email_calendar_binding_receipt import (  # noqa: E402
    DEFAULT_RECEIPT as DEFAULT_BINDING_RECEIPT,
    validate_finance_approval_email_calendar_binding_receipt,
)
from scripts.validate_finance_approval_live_handoff_plan_schema import (  # noqa: E402
    DEFAULT_PLAN as DEFAULT_HANDOFF_PLAN,
    validate_finance_approval_live_handoff_plan_schema,
)
from scripts.validate_finance_approval_live_handoff_closure_run_schema import (  # noqa: E402
    DEFAULT_CLOSURE_RUN,
    validate_finance_approval_live_handoff_closure_run_schema,
)
from scripts.validate_finance_approval_pilot import (  # noqa: E402
    DEFAULT_ADAPTER_EVIDENCE,
    validate_finance_approval_pilot,
)

DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_live_handoff_preflight.json"


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffPreflightStep:
    """One finance live handoff preflight step."""

    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffPreflightReport:
    """Full finance live handoff preflight report."""

    ready: bool
    checked_at: str
    readiness_level: str
    step_count: int
    steps: tuple[FinanceLiveHandoffPreflightStep, ...]
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "checked_at": self.checked_at,
            "readiness_level": self.readiness_level,
            "step_count": self.step_count,
            "steps": [step.as_dict() for step in self.steps],
            "blockers": list(self.blockers),
        }


def preflight_finance_approval_live_handoff(
    *,
    handoff_plan_path: Path = DEFAULT_HANDOFF_PLAN,
    binding_receipt_path: Path = DEFAULT_BINDING_RECEIPT,
    closure_run_path: Path = DEFAULT_CLOSURE_RUN,
    adapter_evidence_path: Path = DEFAULT_ADAPTER_EVIDENCE,
) -> FinanceLiveHandoffPreflightReport:
    """Return read-only finance live handoff preflight status."""
    plan_validation = validate_finance_approval_live_handoff_plan_schema(plan_path=handoff_plan_path)
    binding_validation = validate_finance_approval_email_calendar_binding_receipt(
        receipt_path=binding_receipt_path,
        require_ready=True,
    )
    closure_run_validation = validate_finance_approval_live_handoff_closure_run_schema(
        closure_run_path=closure_run_path,
    )
    readiness = validate_finance_approval_pilot(adapter_evidence_path=adapter_evidence_path)
    steps = (
        FinanceLiveHandoffPreflightStep(
            name="finance handoff plan schema validation",
            passed=plan_validation.ok,
            detail="ok=true" if plan_validation.ok else f"errors={list(plan_validation.errors)}",
        ),
        FinanceLiveHandoffPreflightStep(
            name="finance email/calendar binding receipt ready",
            passed=binding_validation.valid and binding_validation.ready,
            detail=(
                f"valid=true ready=true present={list(binding_validation.present_binding_names)}"
                if binding_validation.valid and binding_validation.ready
                else f"errors={list(binding_validation.errors)} present={list(binding_validation.present_binding_names)}"
            ),
        ),
        FinanceLiveHandoffPreflightStep(
            name="finance live handoff closure run schema validation",
            passed=closure_run_validation.ok,
            detail=(
                f"ok=true status={closure_run_validation.status} live_command_count="
                f"{closure_run_validation.live_command_count}"
                if closure_run_validation.ok
                else f"errors={list(closure_run_validation.errors)}"
            ),
        ),
        FinanceLiveHandoffPreflightStep(
            name="finance approval pilot readiness",
            passed=readiness.ready,
            detail=(
                "readiness_level=live-email-handoff-ready"
                if readiness.ready
                else f"readiness_level={readiness.readiness_level} blockers={list(readiness.blockers)}"
            ),
        ),
    )
    blockers = tuple(step.name for step in steps if not step.passed)
    return FinanceLiveHandoffPreflightReport(
        ready=not blockers,
        checked_at=_validation_clock(),
        readiness_level=readiness.readiness_level,
        step_count=len(steps),
        steps=steps,
        blockers=blockers,
    )


def write_finance_live_handoff_preflight_report(
    report: FinanceLiveHandoffPreflightReport,
    output_path: Path,
) -> Path:
    """Write one finance live handoff preflight report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance handoff preflight arguments."""
    parser = argparse.ArgumentParser(description="Preflight finance approval live handoff readiness.")
    parser.add_argument("--handoff-plan", default=str(DEFAULT_HANDOFF_PLAN))
    parser.add_argument("--binding-receipt", default=str(DEFAULT_BINDING_RECEIPT))
    parser.add_argument("--closure-run", default=str(DEFAULT_CLOSURE_RUN))
    parser.add_argument("--adapter-evidence", default=str(DEFAULT_ADAPTER_EVIDENCE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance handoff preflight."""
    args = parse_args(argv)
    report = preflight_finance_approval_live_handoff(
        handoff_plan_path=Path(args.handoff_plan),
        binding_receipt_path=Path(args.binding_receipt),
        closure_run_path=Path(args.closure_run),
        adapter_evidence_path=Path(args.adapter_evidence),
    )
    write_finance_live_handoff_preflight_report(report, Path(args.output))
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    elif report.ready:
        print("FINANCE LIVE HANDOFF PREFLIGHT READY")
    else:
        print(f"FINANCE LIVE HANDOFF PREFLIGHT BLOCKED blockers={list(report.blockers)}")
    return 0 if report.ready or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
