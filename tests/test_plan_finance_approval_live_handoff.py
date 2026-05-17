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

from scripts.emit_finance_approval_email_calendar_binding_receipt import (
    emit_finance_approval_email_calendar_binding_receipt,
    write_finance_email_calendar_binding_receipt,
)
from scripts.plan_finance_approval_live_handoff import (
    main,
    plan_finance_approval_live_handoff,
    write_finance_live_handoff_plan,
)


def test_current_finance_handoff_plan_scopes_to_email_calendar(tmp_path: Path) -> None:
    evidence_path = _write_open_email_calendar_adapter_evidence(tmp_path)
    plan = plan_finance_approval_live_handoff(
        adapter_evidence_path=evidence_path,
        binding_receipt_path=tmp_path / "missing_binding_receipt.json",
    )
    actions_by_blocker = {action.blocker: action for action in plan.actions}

    assert plan.ready is False
    assert plan.readiness_level in {"not-ready", "proof-pilot-ready"}
    assert plan.action_count >= 1
    assert plan.plan_id.startswith("finance-live-handoff-plan-")
    assert "finance_email_calendar_binding_receipt_not_ready" in plan.blockers
    assert "email_calendar_live_evidence_missing" in plan.blockers
    binding_action = actions_by_blocker["finance_email_calendar_binding_receipt_not_ready"]
    assert "MULLU_EMAIL_CALENDAR_WORKER_URL" in binding_action.command
    assert "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID" in binding_action.command
    assert binding_action.approval_required is True
    assert (
        "worker_endpoint_presence_attestation"
        in binding_action.evidence_required
    )
    assert (
        "worker_secret_presence_attestation"
        in binding_action.evidence_required
    )
    assert (
        "finance_approval_email_calendar_binding_receipt.json"
        in binding_action.evidence_required
    )
    assert "validate_finance_approval_email_calendar_binding_receipt.py" in binding_action.verification_command
    assert "--require-ready" in binding_action.verification_command
    assert "finance_email_calendar_binding_receipt.ready" in binding_action.receipt_validator
    assert actions_by_blocker["email_calendar_live_evidence_missing"].approval_required is False
    assert "--email-calendar-connector-id <connector_id>" in actions_by_blocker[
        "email_calendar_live_evidence_missing"
    ].command
    assert "--email-calendar-query <read_only_query>" in actions_by_blocker[
        "email_calendar_live_evidence_missing"
    ].command
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
    binding_receipt_path = _write_ready_binding_receipt(tmp_path)
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

    plan = plan_finance_approval_live_handoff(
        adapter_evidence_path=evidence_path,
        binding_receipt_path=binding_receipt_path,
    )

    assert plan.ready is True
    assert plan.readiness_level == "live-email-handoff-ready"
    assert plan.action_count == 0
    assert plan.blockers == ()
    assert plan.actions == ()


def test_finance_handoff_plan_writer_and_cli_emit_json(tmp_path: Path, capsys) -> None:
    evidence_path = _write_open_email_calendar_adapter_evidence(tmp_path)
    binding_receipt_path = tmp_path / "missing_binding_receipt.json"
    output_path = tmp_path / "finance_approval_live_handoff_plan.json"
    plan = plan_finance_approval_live_handoff(
        adapter_evidence_path=evidence_path,
        binding_receipt_path=binding_receipt_path,
    )

    written = write_finance_live_handoff_plan(plan, output_path)
    exit_code = main(
        [
            "--adapter-evidence",
            str(evidence_path),
            "--binding-receipt",
            str(binding_receipt_path),
            "--output",
            str(output_path),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert written_payload["plan_id"] == stdout_payload["plan_id"]
    assert written_payload["action_count"] == 2
    assert stdout_payload["ready"] is False
    assert "finance_email_calendar_binding_receipt_not_ready" in stdout_payload["blockers"]


def _write_open_email_calendar_adapter_evidence(tmp_path: Path) -> Path:
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
                        "status": "open",
                        "blockers": [
                            "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN",
                            "email_calendar_live_evidence_missing",
                        ],
                        "evidence_refs": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return evidence_path


def _write_ready_binding_receipt(tmp_path: Path) -> Path:
    receipt_path = tmp_path / "finance_approval_email_calendar_binding_receipt.json"
    receipt, errors = emit_finance_approval_email_calendar_binding_receipt(env_reader=_ready_env)
    write_finance_email_calendar_binding_receipt(receipt, receipt_path)
    assert errors == ()
    return receipt_path


def _ready_env(name: str) -> str:
    values = {
        "MULLU_EMAIL_CALENDAR_WORKER_URL": "https://email-calendar.internal/execute",
        "MULLU_EMAIL_CALENDAR_WORKER_SECRET": "secret-worker-value",
        "GMAIL_ACCESS_TOKEN": "secret-token-value",
        "GMAIL_SCOPE_ID": "gmail.readonly",
    }
    return values.get(name, "")
