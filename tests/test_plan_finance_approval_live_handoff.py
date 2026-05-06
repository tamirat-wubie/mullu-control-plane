"""Tests for finance approval live handoff planning.

Purpose: prove finance pilot blockers become narrowly scoped email/calendar
handoff actions.
Governance scope: finance readiness, credential binding, live receipt planning,
and no false production claims.
Dependencies: scripts.plan_finance_approval_live_handoff.
Invariants:
  - Current finance readiness emits only email/calendar closure actions.
  - Credential binding requires approval.
  - Closed email/calendar evidence emits an empty plan.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.plan_finance_approval_live_handoff import (
    main,
    plan_finance_approval_live_handoff,
    write_finance_live_handoff_plan,
)


def test_current_finance_handoff_plan_scopes_to_email_calendar() -> None:
    plan = plan_finance_approval_live_handoff()
    actions_by_blocker = {action.blocker: action for action in plan.actions}

    assert plan.ready is False
    assert plan.readiness_level == "proof-pilot-ready"
    assert plan.action_count == 2
    assert plan.plan_id.startswith("finance-live-handoff-plan-")
    assert plan.blockers == (
        "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN",
        "email_calendar_live_evidence_missing",
    )
    assert actions_by_blocker[
        "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN"
    ].approval_required is True
    assert (
        "finance_approval_email_calendar_binding_receipt.json"
        in actions_by_blocker[
            "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN"
        ].evidence_required
    )
    assert "validate_finance_approval_email_calendar_binding_receipt.py" in actions_by_blocker[
        "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN"
    ].verification_command
    assert "--require-ready" in actions_by_blocker[
        "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN"
    ].verification_command
    assert actions_by_blocker["email_calendar_live_evidence_missing"].approval_required is False
    assert (
        "validate_finance_approval_email_calendar_live_receipt.py"
        in actions_by_blocker["email_calendar_live_evidence_missing"].verification_command
    )
    assert (
        "finance_email_calendar_live_receipt.ready"
        in actions_by_blocker["email_calendar_live_evidence_missing"].receipt_validator
    )
    assert "browser_live_evidence_missing" not in plan.blockers
    assert "voice_live_evidence_missing" not in plan.blockers


def test_finance_handoff_plan_empty_when_email_calendar_evidence_closed(tmp_path: Path) -> None:
    evidence_path = tmp_path / "capability_adapter_evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "adapters": [
                    {
                        "adapter_id": "document.production_parsers",
                        "status": "closed",
                        "blockers": [],
                        "evidence_refs": ["document_live_receipt.json"],
                    },
                    {
                        "adapter_id": "communication.email_calendar_worker",
                        "status": "closed",
                        "blockers": [],
                        "evidence_refs": ["email_calendar_live_receipt.json"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    plan = plan_finance_approval_live_handoff(adapter_evidence_path=evidence_path)

    assert plan.ready is True
    assert plan.readiness_level == "live-email-handoff-ready"
    assert plan.action_count == 0
    assert plan.blockers == ()
    assert plan.actions == ()


def test_finance_handoff_plan_writer_and_cli_emit_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "finance_approval_live_handoff_plan.json"
    plan = plan_finance_approval_live_handoff()

    written = write_finance_live_handoff_plan(plan, output_path)
    exit_code = main(["--output", str(output_path), "--json"])
    captured = capsys.readouterr()
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert written_payload["plan_id"] == stdout_payload["plan_id"]
    assert written_payload["action_count"] == 2
    assert stdout_payload["ready"] is False
