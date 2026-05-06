#!/usr/bin/env python3
"""Validate the finance approval live handoff artifact chain.

Purpose: aggregate finance closure-run, live receipt, preflight,
handoff-packet, and protocol manifest validation into one read-only operator
check.
Governance scope: finance live handoff artifact chain consistency, schema
validation aggregation, manifest completeness, and explicit blocker reporting.
Dependencies: finance closure-run schema validation, finance live receipt
validation, finance preflight schema validation, finance handoff packet schema
validation, and governance protocol manifest validation.
Invariants:
  - Chain validation never executes live adapter receipts.
  - All referenced validators remain read-only.
  - Any failed child validator fails the chain.
  - Protocol manifest errors remain explicit blockers.
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

from scripts.validate_finance_approval_handoff_packet_schema import (  # noqa: E402
    DEFAULT_PACKET,
    validate_finance_approval_handoff_packet_schema,
)
from scripts.validate_finance_approval_email_calendar_live_receipt import (  # noqa: E402
    DEFAULT_EMAIL_CALENDAR_RECEIPT,
    validate_finance_approval_email_calendar_live_receipt,
)
from scripts.validate_finance_approval_live_handoff_closure_run_schema import (  # noqa: E402
    DEFAULT_CLOSURE_RUN,
    validate_finance_approval_live_handoff_closure_run_schema,
)
from scripts.validate_finance_approval_live_handoff_preflight_schema import (  # noqa: E402
    DEFAULT_PREFLIGHT,
    validate_finance_approval_live_handoff_preflight_schema,
)
from scripts.validate_protocol_manifest import load_manifest, validate_protocol_manifest  # noqa: E402

DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_live_handoff_chain_validation.json"


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffChainCheck:
    """One validation result within the finance handoff chain."""

    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffChainValidation:
    """Validation report for the finance live handoff artifact chain."""

    ok: bool
    ready: bool
    checked_at: str
    check_count: int
    checks: tuple[FinanceLiveHandoffChainCheck, ...]
    blockers: tuple[str, ...]
    readiness_blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "ready": self.ready,
            "checked_at": self.checked_at,
            "check_count": self.check_count,
            "checks": [check.as_dict() for check in self.checks],
            "blockers": list(self.blockers),
            "readiness_blockers": list(self.readiness_blockers),
        }


def validate_finance_approval_live_handoff_chain(
    *,
    closure_run_path: Path = DEFAULT_CLOSURE_RUN,
    live_receipt_path: Path = DEFAULT_EMAIL_CALENDAR_RECEIPT,
    preflight_path: Path = DEFAULT_PREFLIGHT,
    packet_path: Path = DEFAULT_PACKET,
) -> FinanceLiveHandoffChainValidation:
    """Return read-only validation for the finance live handoff chain."""
    closure_validation = validate_finance_approval_live_handoff_closure_run_schema(
        closure_run_path=closure_run_path,
    )
    live_receipt_validation = validate_finance_approval_email_calendar_live_receipt(
        receipt_path=live_receipt_path,
    )
    preflight_validation = validate_finance_approval_live_handoff_preflight_schema(
        preflight_path=preflight_path,
    )
    packet_validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
    )
    manifest_errors = tuple(validate_protocol_manifest(load_manifest()))
    checks = (
        FinanceLiveHandoffChainCheck(
            name="finance closure run schema validation",
            passed=closure_validation.ok,
            detail=(
                f"command_count={closure_validation.command_count} live_command_count="
                f"{closure_validation.live_command_count} status={closure_validation.status}"
                if closure_validation.ok
                else f"errors={list(closure_validation.errors)}"
            ),
        ),
        FinanceLiveHandoffChainCheck(
            name="finance email/calendar live receipt validation",
            passed=live_receipt_validation.valid,
            detail=(
                f"ready={live_receipt_validation.ready} status={live_receipt_validation.status} "
                f"verification_status={live_receipt_validation.verification_status} "
                f"external_write={live_receipt_validation.external_write} "
                f"blockers={list(live_receipt_validation.blockers)}"
                if live_receipt_validation.valid
                else f"errors={list(live_receipt_validation.errors)}"
            ),
        ),
        FinanceLiveHandoffChainCheck(
            name="finance preflight schema validation",
            passed=preflight_validation.ok,
            detail=(
                f"step_count={preflight_validation.step_count} blocker_count="
                f"{preflight_validation.blocker_count} readiness_level={preflight_validation.readiness_level}"
                if preflight_validation.ok
                else f"errors={list(preflight_validation.errors)}"
            ),
        ),
        FinanceLiveHandoffChainCheck(
            name="finance handoff packet schema validation",
            passed=packet_validation.ok,
            detail=(
                f"artifact_count={packet_validation.artifact_count} blocker_count="
                f"{packet_validation.blocker_count} readiness_level={packet_validation.readiness_level}"
                if packet_validation.ok
                else f"errors={list(packet_validation.errors)}"
            ),
        ),
        FinanceLiveHandoffChainCheck(
            name="governance protocol manifest validation",
            passed=not manifest_errors,
            detail="ok=true" if not manifest_errors else f"errors={list(manifest_errors)}",
        ),
    )
    blockers = tuple(check.name for check in checks if not check.passed)
    readiness_blockers = _readiness_blockers(
        validation_blockers=blockers,
        closure_validation=closure_validation,
        live_receipt_validation=live_receipt_validation,
        preflight_validation=preflight_validation,
        packet_validation=packet_validation,
        manifest_errors=manifest_errors,
    )
    return FinanceLiveHandoffChainValidation(
        ok=not blockers,
        ready=not blockers and not readiness_blockers,
        checked_at=_validation_clock(),
        check_count=len(checks),
        checks=checks,
        blockers=blockers,
        readiness_blockers=readiness_blockers,
    )


def write_finance_live_handoff_chain_validation(
    validation: FinanceLiveHandoffChainValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic finance live handoff chain validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def _readiness_blockers(
    *,
    validation_blockers: tuple[str, ...],
    closure_validation: Any,
    live_receipt_validation: Any,
    preflight_validation: Any,
    packet_validation: Any,
    manifest_errors: tuple[str, ...],
) -> tuple[str, ...]:
    """Return operator-readiness blockers without weakening schema validation."""
    blockers = list(validation_blockers)
    if closure_validation.ok and closure_validation.status != "ready":
        blockers.append(f"finance closure run not ready: status={closure_validation.status}")
    if live_receipt_validation.valid and not live_receipt_validation.ready:
        blockers.append(
            "finance email/calendar live receipt not ready: "
            f"status={live_receipt_validation.status} blockers={list(live_receipt_validation.blockers)}"
        )
    if preflight_validation.ok and preflight_validation.blocker_count:
        blockers.append(f"finance preflight not ready: blocker_count={preflight_validation.blocker_count}")
    if packet_validation.ok and packet_validation.blocker_count:
        blockers.append(f"finance handoff packet not ready: blocker_count={packet_validation.blocker_count}")
    if manifest_errors:
        blockers.append("governance protocol manifest validation failed")
    return tuple(dict.fromkeys(blockers))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance live handoff chain validation arguments."""
    parser = argparse.ArgumentParser(description="Validate finance approval live handoff artifact chain.")
    parser.add_argument("--closure-run", default=str(DEFAULT_CLOSURE_RUN))
    parser.add_argument("--live-receipt", default=str(DEFAULT_EMAIL_CALENDAR_RECEIPT))
    parser.add_argument("--preflight", default=str(DEFAULT_PREFLIGHT))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance live handoff chain validation."""
    args = parse_args(argv)
    validation = validate_finance_approval_live_handoff_chain(
        closure_run_path=Path(args.closure_run),
        live_receipt_path=Path(args.live_receipt),
        preflight_path=Path(args.preflight),
        packet_path=Path(args.packet),
    )
    write_finance_live_handoff_chain_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("FINANCE LIVE HANDOFF CHAIN VALID")
    else:
        print(f"FINANCE LIVE HANDOFF CHAIN INVALID blockers={list(validation.blockers)}")
    if args.require_ready and not validation.ready:
        return 2
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
