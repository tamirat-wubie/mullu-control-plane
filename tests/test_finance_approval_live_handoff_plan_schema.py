"""Tests for finance approval live handoff plan schema validation.

Purpose: prove finance handoff plans are public-schema aligned and restricted
to email/calendar closure.
Governance scope: finance handoff schema, blocker scope, approval gating, and
read-only receipt proof contracts.
Dependencies: scripts.validate_finance_approval_live_handoff_plan_schema and
schemas/finance_approval_live_handoff_plan.schema.json.
Invariants:
  - Valid finance handoff plans pass schema and semantic validation.
  - Browser or voice blockers fail closed.
  - Credential actions require approval and scope evidence.
  - Live receipt actions require read-only email/calendar evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_finance_approval_live_handoff_plan_schema import (
    main,
    validate_finance_approval_live_handoff_plan_schema,
    write_finance_live_handoff_plan_schema_validation,
)

_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = _ROOT / "schemas" / "finance_approval_live_handoff_plan.schema.json"


def test_finance_handoff_plan_schema_accepts_valid_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "finance_approval_live_handoff_plan.json"
    plan_path.write_text(json.dumps(_valid_plan()), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.action_count == 2
    assert validation.approval_required_action_count == 1
    assert validation.blocker_count == 2


def test_finance_handoff_plan_schema_rejects_count_drift(tmp_path: Path) -> None:
    plan_path = tmp_path / "finance_approval_live_handoff_plan.json"
    payload = _valid_plan()
    payload["action_count"] = 99
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "action_count does not match actions length" in validation.errors


def test_finance_handoff_plan_schema_rejects_out_of_scope_blocker(tmp_path: Path) -> None:
    plan_path = tmp_path / "finance_approval_live_handoff_plan.json"
    payload = _valid_plan()
    payload["blockers"].append("voice_live_evidence_missing")
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("voice_live_evidence_missing" in error for error in validation.errors)


def test_finance_handoff_plan_schema_rejects_uncovered_blocker(tmp_path: Path) -> None:
    plan_path = tmp_path / "finance_approval_live_handoff_plan.json"
    payload = _valid_plan()
    payload["actions"] = payload["actions"][:1]
    payload["action_count"] = 1
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("email_calendar_live_evidence_missing" in error for error in validation.errors)
    assert any("missing closure actions" in error for error in validation.errors)


def test_finance_handoff_plan_schema_requires_credential_approval(tmp_path: Path) -> None:
    plan_path = tmp_path / "finance_approval_live_handoff_plan.json"
    payload = _valid_plan()
    payload["actions"][0]["approval_required"] = False
    payload["actions"][0]["evidence_required"] = ["secret_presence_attestation"]
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("must require approval" in error for error in validation.errors)
    assert any("connector_scope_attestation" in error for error in validation.errors)


def test_finance_handoff_plan_schema_requires_binding_receipt_ready_gate(tmp_path: Path) -> None:
    plan_path = tmp_path / "finance_approval_live_handoff_plan.json"
    payload = _valid_plan()
    payload["actions"][0]["verification_command"] = (
        "python scripts/collect_capability_adapter_evidence.py "
        "--output .change_assurance/capability_adapter_evidence.json"
    )
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("validate_finance_approval_email_calendar_binding_receipt.py" in error for error in validation.errors)
    assert any("--require-ready" in error for error in validation.errors)


def test_finance_handoff_plan_schema_requires_read_only_receipt_gate(tmp_path: Path) -> None:
    plan_path = tmp_path / "finance_approval_live_handoff_plan.json"
    payload = _valid_plan()
    payload["actions"][1]["command"] = "python scripts/produce_capability_adapter_live_receipts.py"
    payload["actions"][1]["evidence_required"] = ["email_calendar_live_receipt.json"]
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("--target email-calendar" in error for error in validation.errors)
    assert any("validate_finance_approval_email_calendar_live_receipt.py" in error for error in validation.errors)
    assert any("read_only_probe_receipt" in error for error in validation.errors)


def test_finance_handoff_plan_schema_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    plan_path = tmp_path / "finance_approval_live_handoff_plan.json"
    output_path = tmp_path / "schema_validation.json"
    plan_path.write_text(json.dumps(_valid_plan()), encoding="utf-8")
    validation = validate_finance_approval_live_handoff_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_finance_live_handoff_plan_schema_validation(validation, output_path)
    exit_code = main(
        [
            "--plan",
            str(plan_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["action_count"] == 2


def _valid_plan() -> dict[str, object]:
    return {
        "plan_id": "finance-live-handoff-plan-0123456789abcdef",
        "readiness_level": "proof-pilot-ready",
        "ready": False,
        "action_count": 2,
        "blockers": [
            "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN",
            "email_calendar_live_evidence_missing",
        ],
        "actions": [
            {
                "action_id": "finance-email-calendar-token-binding",
                "blocker": "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN",
                "action_type": "credential",
                "command": (
                    "Bind one scoped read-capable connector token in the governed worker secret store: "
                    "GMAIL_ACCESS_TOKEN, GOOGLE_CALENDAR_ACCESS_TOKEN, or MICROSOFT_GRAPH_ACCESS_TOKEN."
                ),
                "verification_command": (
                    "python scripts/validate_finance_approval_email_calendar_binding_receipt.py "
                    "--require-ready --json && "
                    "python scripts/collect_capability_adapter_evidence.py "
                    "--output .change_assurance/capability_adapter_evidence.json"
                ),
                "receipt_validator": "adapter_evidence.communication.email_calendar_worker.dependency.EMAIL_CALENDAR_CONNECTOR_TOKEN",
                "evidence_required": [
                    "connector_scope_attestation",
                    "secret_presence_attestation",
                    "finance_approval_email_calendar_binding_receipt.json",
                ],
                "approval_required": True,
            },
            {
                "action_id": "finance-email-calendar-read-only-live-receipt",
                "blocker": "email_calendar_live_evidence_missing",
                "action_type": "live-receipt",
                "command": "python scripts/produce_capability_adapter_live_receipts.py --target email-calendar --strict",
                "verification_command": (
                    "python scripts/validate_finance_approval_email_calendar_live_receipt.py "
                    "--require-ready --json && "
                    "python scripts/validate_finance_approval_pilot.py "
                    "--output .change_assurance/finance_approval_readiness.json --json"
                ),
                "receipt_validator": (
                    "finance_email_calendar_live_receipt.ready && "
                    "finance_readiness.email_calendar_evidence_closed"
                ),
                "evidence_required": [
                    "email_calendar_live_receipt.json",
                    "read_only_probe_receipt",
                ],
                "approval_required": False,
            },
        ],
    }
