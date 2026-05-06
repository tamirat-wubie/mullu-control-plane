#!/usr/bin/env python3
"""Plan finance approval packet live email handoff closure.

Purpose: convert finance approval pilot readiness blockers into the exact
operator actions needed to promote from proof-pilot-ready to
live-email-handoff-ready.
Governance scope: finance approval packet readiness, email/calendar connector
credential binding, read-only live receipt production, and adapter evidence
collection.
Dependencies: scripts.validate_finance_approval_pilot and capability adapter
evidence artifacts.
Invariants:
  - Planning never claims live email delivery.
  - Only finance-relevant email/calendar blockers are emitted.
  - Credential actions require approval and scope evidence.
  - Live receipt actions require read-only worker evidence.
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

from scripts.validate_finance_approval_pilot import (  # noqa: E402  # noqa: E402
    DEFAULT_ADAPTER_EVIDENCE,
    FinancePilotReadiness,
    validate_finance_approval_pilot,
)

DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_live_handoff_plan.json"


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffAction:
    """One finance live handoff closure action."""

    action_id: str
    blocker: str
    action_type: str
    command: str
    verification_command: str
    receipt_validator: str
    evidence_required: tuple[str, ...]
    approval_required: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_required"] = list(self.evidence_required)
        return payload


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffPlan:
    """Finance pilot live email handoff promotion plan."""

    plan_id: str
    readiness_level: str
    ready: bool
    action_count: int
    blockers: tuple[str, ...]
    actions: tuple[FinanceLiveHandoffAction, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "readiness_level": self.readiness_level,
            "ready": self.ready,
            "action_count": self.action_count,
            "blockers": list(self.blockers),
            "actions": [action.as_dict() for action in self.actions],
        }


def plan_finance_approval_live_handoff(
    *,
    adapter_evidence_path: Path = DEFAULT_ADAPTER_EVIDENCE,
) -> FinanceLiveHandoffPlan:
    """Return the finance-specific live email handoff closure plan."""
    readiness = validate_finance_approval_pilot(adapter_evidence_path=adapter_evidence_path)
    email_check = _email_calendar_check(readiness)
    blockers = _finance_email_blockers(readiness, email_check)
    actions = tuple(_action_for(blocker) for blocker in blockers)
    _validate_actions(actions)
    material = {
        "readiness_level": readiness.readiness_level,
        "ready": readiness.ready,
        "blockers": blockers,
        "actions": [action.as_dict() for action in actions],
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return FinanceLiveHandoffPlan(
        plan_id=f"finance-live-handoff-plan-{digest[:16]}",
        readiness_level=readiness.readiness_level,
        ready=readiness.ready,
        action_count=len(actions),
        blockers=blockers,
        actions=actions,
    )


def write_finance_live_handoff_plan(plan: FinanceLiveHandoffPlan, output_path: Path) -> Path:
    """Write one finance live handoff plan."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _email_calendar_check(readiness: FinancePilotReadiness) -> dict[str, Any]:
    for check in readiness.checks:
        if check.get("name") == "email calendar evidence closed":
            return dict(check)
    return {
        "name": "email calendar evidence closed",
        "passed": False,
        "detail": "email/calendar readiness check missing",
        "evidence_refs": [],
    }


def _finance_email_blockers(readiness: FinancePilotReadiness, email_check: dict[str, Any]) -> tuple[str, ...]:
    if readiness.ready:
        return ()
    blockers: list[str] = []
    detail = str(email_check.get("detail", ""))
    if "EMAIL_CALENDAR_CONNECTOR_TOKEN" in detail:
        blockers.append("email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN")
    if email_check.get("passed") is not True:
        blockers.append("email_calendar_live_evidence_missing")
    if "email calendar evidence closed" in readiness.blockers and not blockers:
        blockers.append("email_calendar_evidence_not_closed")
    return tuple(dict.fromkeys(blockers))


def _action_for(blocker: str) -> FinanceLiveHandoffAction:
    if blocker == "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN":
        return FinanceLiveHandoffAction(
            action_id="finance-email-calendar-token-binding",
            blocker=blocker,
            action_type="credential",
            command=(
                "Bind one scoped read-capable connector token in the governed worker secret store: "
                "GMAIL_ACCESS_TOKEN, GOOGLE_CALENDAR_ACCESS_TOKEN, or MICROSOFT_GRAPH_ACCESS_TOKEN. "
                "Then run python scripts/emit_finance_approval_email_calendar_binding_receipt.py --strict"
            ),
            verification_command=(
                "python scripts/validate_finance_approval_email_calendar_binding_receipt.py "
                "--require-ready --json && "
                "python scripts/collect_capability_adapter_evidence.py "
                "--output .change_assurance/capability_adapter_evidence.json"
            ),
            receipt_validator="adapter_evidence.communication.email_calendar_worker.dependency.EMAIL_CALENDAR_CONNECTOR_TOKEN",
            evidence_required=(
                "connector_scope_attestation",
                "secret_presence_attestation",
                "finance_approval_email_calendar_binding_receipt.json",
            ),
            approval_required=True,
        )
    if blocker == "email_calendar_live_evidence_missing":
        return FinanceLiveHandoffAction(
            action_id="finance-email-calendar-read-only-live-receipt",
            blocker=blocker,
            action_type="live-receipt",
            command="python scripts/produce_capability_adapter_live_receipts.py --target email-calendar --strict",
            verification_command=(
                "python scripts/validate_finance_approval_email_calendar_live_receipt.py "
                "--require-ready --json && "
                "python scripts/validate_finance_approval_pilot.py "
                "--output .change_assurance/finance_approval_readiness.json --json"
            ),
            receipt_validator="finance_email_calendar_live_receipt.ready && finance_readiness.email_calendar_evidence_closed",
            evidence_required=("email_calendar_live_receipt.json", "read_only_probe_receipt"),
            approval_required=False,
        )
    return FinanceLiveHandoffAction(
        action_id="finance-email-calendar-manual-review",
        blocker=blocker,
        action_type="manual-review",
        command="Review finance email/calendar blocker and add a governed closure action.",
        verification_command="python scripts/plan_finance_approval_live_handoff.py --json",
        receipt_validator="manual_review_receipt.present",
        evidence_required=("manual_review_receipt",),
        approval_required=True,
    )


def _validate_actions(actions: tuple[FinanceLiveHandoffAction, ...]) -> None:
    for action in actions:
        if not action.command.strip():
            raise ValueError(f"command is required for finance handoff action: {action.action_id}")
        if not action.verification_command.strip():
            raise ValueError(f"verification_command is required for finance handoff action: {action.action_id}")
        if not action.receipt_validator.strip():
            raise ValueError(f"receipt_validator is required for finance handoff action: {action.action_id}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan finance approval live email handoff closure.")
    parser.add_argument("--adapter-evidence", default=str(DEFAULT_ADAPTER_EVIDENCE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = plan_finance_approval_live_handoff(adapter_evidence_path=Path(args.adapter_evidence))
    write_finance_live_handoff_plan(plan, Path(args.output))
    if args.json:
        print(json.dumps(plan.as_dict(), indent=2, sort_keys=True))
    elif plan.ready:
        print(f"FINANCE LIVE HANDOFF READY plan_id={plan.plan_id}")
    else:
        print(f"FINANCE LIVE HANDOFF PLAN WRITTEN actions={plan.action_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

