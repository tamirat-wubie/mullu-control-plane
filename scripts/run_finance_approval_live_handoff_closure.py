#!/usr/bin/env python3
"""Dry-run the finance approval live handoff closure sequence.

Purpose: produce one governed command sequence for promoting the finance
approval packet pilot from proof-pilot-ready to live-email-handoff-ready.
Governance scope: finance approval email/calendar binding, read-only live
receipt collection, readiness validation, preflight validation, packet schema
validation, aggregate chain validation, and operator summary publication.
Dependencies: finance binding receipt validation and finance pilot readiness
validation.
Invariants:
  - Default mode never executes commands.
  - Secret values are never read or serialized.
  - Live connector touchpoints are explicitly marked.
  - Binding readiness is checked before live email/calendar receipt collection.
"""

from __future__ import annotations

import argparse
import hashlib
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
from scripts.validate_finance_approval_pilot import (  # noqa: E402
    DEFAULT_ADAPTER_EVIDENCE,
    validate_finance_approval_pilot,
)

DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_live_handoff_closure_run.json"


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffClosureCommand:
    """One governed command in the finance live handoff closure sequence."""

    step_id: str
    purpose: str
    command: str
    required_before_next: bool
    live_effect_possible: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffClosureRun:
    """Dry-run record for finance live handoff closure."""

    run_id: str
    checked_at: str
    mode: str
    status: str
    ready_to_execute_live: bool
    command_count: int
    blockers: tuple[str, ...]
    commands: tuple[FinanceLiveHandoffClosureCommand, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "checked_at": self.checked_at,
            "mode": self.mode,
            "status": self.status,
            "ready_to_execute_live": self.ready_to_execute_live,
            "command_count": self.command_count,
            "blockers": list(self.blockers),
            "commands": [command.as_dict() for command in self.commands],
        }


def run_finance_approval_live_handoff_closure(
    *,
    binding_receipt_path: Path = DEFAULT_BINDING_RECEIPT,
    adapter_evidence_path: Path = DEFAULT_ADAPTER_EVIDENCE,
) -> FinanceLiveHandoffClosureRun:
    """Return a dry-run closure record without executing live commands."""
    commands = _closure_commands()
    binding_validation = validate_finance_approval_email_calendar_binding_receipt(
        receipt_path=binding_receipt_path,
        require_ready=True,
    )
    readiness = validate_finance_approval_pilot(adapter_evidence_path=adapter_evidence_path)
    blockers = _closure_blockers(binding_validation_valid=binding_validation.valid, readiness_ready=readiness.ready)
    material = {
        "mode": "dry-run",
        "blockers": blockers,
        "commands": [command.as_dict() for command in commands],
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return FinanceLiveHandoffClosureRun(
        run_id=f"finance-live-handoff-closure-run-{digest[:16]}",
        checked_at=_validation_clock(),
        mode="dry-run",
        status="ready" if not blockers else "blocked",
        ready_to_execute_live=not blockers,
        command_count=len(commands),
        blockers=blockers,
        commands=commands,
    )


def write_finance_live_handoff_closure_run(run: FinanceLiveHandoffClosureRun, output_path: Path) -> Path:
    """Write one finance live handoff closure run record."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(run.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _closure_commands() -> tuple[FinanceLiveHandoffClosureCommand, ...]:
    return (
        FinanceLiveHandoffClosureCommand(
            step_id="01_emit_binding_receipt",
            purpose="Record redacted token-name presence for approved email/calendar connector bindings.",
            command=(
                "python scripts/emit_finance_approval_email_calendar_binding_receipt.py "
                "--output .change_assurance/finance_approval_email_calendar_binding_receipt.json --strict --json"
            ),
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="02_validate_binding_receipt",
            purpose="Fail closed until one accepted connector binding is present and schema-valid.",
            command="python scripts/validate_finance_approval_email_calendar_binding_receipt.py --require-ready --json",
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="03_collect_read_only_live_receipt",
            purpose="Produce the read-only email/calendar live receipt after binding readiness is proven.",
            command="python scripts/produce_capability_adapter_live_receipts.py --target email-calendar --strict --json",
            required_before_next=True,
            live_effect_possible=True,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="04_validate_read_only_live_receipt",
            purpose="Fail closed unless the email/calendar live receipt is passed, read-only, and adapter-bound.",
            command="python scripts/validate_finance_approval_email_calendar_live_receipt.py --require-ready --json",
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="05_collect_adapter_evidence",
            purpose="Collect capability adapter evidence from the newly produced live receipt.",
            command=(
                "python scripts/collect_capability_adapter_evidence.py "
                "--output .change_assurance/capability_adapter_evidence.json --json"
            ),
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="06_validate_pilot_readiness",
            purpose="Recompute finance approval pilot readiness from adapter evidence.",
            command=(
                "python scripts/validate_finance_approval_pilot.py "
                "--output .change_assurance/finance_approval_readiness.json --json"
            ),
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="07_refresh_handoff_plan",
            purpose="Refresh the finance live handoff plan after evidence collection.",
            command=(
                "python scripts/plan_finance_approval_live_handoff.py "
                "--output .change_assurance/finance_approval_live_handoff_plan.json --json"
            ),
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="08_validate_handoff_plan_schema",
            purpose="Validate the finance live handoff plan schema and finance-only blocker boundary.",
            command="python scripts/validate_finance_approval_live_handoff_plan_schema.py --strict --json",
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="09_run_preflight",
            purpose="Run strict finance handoff preflight before updating the final packet.",
            command=(
                "python scripts/preflight_finance_approval_live_handoff.py "
                "--output .change_assurance/finance_approval_live_handoff_preflight.json --strict --json"
            ),
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="10_validate_preflight_schema",
            purpose="Validate the strict four-step finance handoff preflight report.",
            command="python scripts/validate_finance_approval_live_handoff_preflight_schema.py --strict --json",
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="11_produce_handoff_packet",
            purpose="Produce the bounded finance approval handoff packet.",
            command=(
                "python scripts/produce_finance_approval_handoff_packet.py "
                "--output .change_assurance/finance_approval_handoff_packet.json --json"
            ),
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="12_validate_handoff_packet_schema",
            purpose="Validate the final finance approval handoff packet schema.",
            command="python scripts/validate_finance_approval_handoff_packet_schema.py --strict --json",
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="13_validate_handoff_chain",
            purpose="Validate the aggregate finance live handoff artifact chain.",
            command="python scripts/validate_finance_approval_live_handoff_chain.py --strict --require-ready --json",
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="14_validate_handoff_chain_schema",
            purpose="Validate the aggregate finance live handoff chain validation report schema.",
            command="python scripts/validate_finance_approval_live_handoff_chain_schema.py --strict --json",
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="15_produce_operator_summary",
            purpose="Produce the operator-facing finance handoff summary from the bounded packet and chain result.",
            command=(
                "python scripts/produce_finance_approval_operator_summary.py "
                "--output .change_assurance/finance_approval_operator_summary.json --strict --json"
            ),
            required_before_next=True,
            live_effect_possible=False,
        ),
        FinanceLiveHandoffClosureCommand(
            step_id="16_validate_operator_summary_schema",
            purpose="Validate the operator summary schema and promotion-claim guardrails.",
            command="python scripts/validate_finance_approval_operator_summary_schema.py --strict --json",
            required_before_next=True,
            live_effect_possible=False,
        ),
    )


def _closure_blockers(*, binding_validation_valid: bool, readiness_ready: bool) -> tuple[str, ...]:
    blockers: list[str] = []
    if not binding_validation_valid:
        blockers.append("finance_email_calendar_binding_receipt_not_ready")
    if not readiness_ready:
        blockers.append("finance_approval_pilot_readiness_not_ready")
    return tuple(blockers)


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance live handoff closure runner arguments."""
    parser = argparse.ArgumentParser(description="Dry-run finance approval live handoff closure.")
    parser.add_argument("--binding-receipt", default=str(DEFAULT_BINDING_RECEIPT))
    parser.add_argument("--adapter-evidence", default=str(DEFAULT_ADAPTER_EVIDENCE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance live handoff closure dry-run."""
    args = parse_args(argv)
    run = run_finance_approval_live_handoff_closure(
        binding_receipt_path=Path(args.binding_receipt),
        adapter_evidence_path=Path(args.adapter_evidence),
    )
    write_finance_live_handoff_closure_run(run, Path(args.output))
    if args.json:
        print(json.dumps(run.as_dict(), indent=2, sort_keys=True))
    elif run.status == "ready":
        print(f"FINANCE LIVE HANDOFF CLOSURE READY run_id={run.run_id}")
    else:
        print(f"FINANCE LIVE HANDOFF CLOSURE BLOCKED blockers={list(run.blockers)}")
    return 0 if run.status == "ready" or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
