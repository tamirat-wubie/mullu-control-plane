"""Tests for finance email/calendar operator input requests.

Purpose: prove blocked finance email/calendar binding receipts become
public-safe operator input requests.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.emit_finance_approval_email_calendar_operator_input_request.
Invariants:
  - Missing worker, connector, and scope inputs are explicit.
  - Secret values, worker URLs, scope values, and provider account details are not serialized.
  - Ready binding receipts do not block finance email/calendar handoff.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.emit_finance_approval_email_calendar_operator_input_request import (  # noqa: E402
    emit_finance_email_calendar_operator_input_request,
    main,
    write_finance_email_calendar_operator_input_request,
)

SCHEMA_PATH = _ROOT / "schemas" / "finance_approval_email_calendar_operator_input_request.schema.json"


def test_operator_input_request_reports_missing_finance_bindings(tmp_path: Path) -> None:
    receipt_path = _write_blocked_binding_receipt(tmp_path)

    request = emit_finance_email_calendar_operator_input_request(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )
    input_kinds = {item.input_kind for item in request.required_inputs}
    required_names = {name for item in request.required_inputs for name in item.required_names}
    rendered = json.dumps(request.as_dict(), sort_keys=True)

    assert request.request_id.startswith("finance-email-calendar-operator-input-request-")
    assert request.ready is False
    assert request.handoff_allowed is False
    assert request.solver_outcome == "AwaitingEvidence"
    assert request.proof_state == "Unknown"
    assert request.no_secret_values_serialized is True
    assert set(request.blocked_actions) == {
        "customer_or_external_email_dispatch",
        "email_calendar_live_probe",
        "finance_approval_live_handoff",
        "finance_approval_production_readiness_claim",
    }
    assert {"worker_endpoint", "worker_secret", "connector_token", "read_only_scope_witness"} <= input_kinds
    assert {
        "MULLU_EMAIL_CALENDAR_WORKER_URL",
        "MULLU_EMAIL_CALENDAR_WORKER_SECRET",
        "EMAIL_CALENDAR_CONNECTOR_TOKEN",
        "GMAIL_ACCESS_TOKEN",
        "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID",
        "GMAIL_SCOPE_ID",
    } <= required_names
    assert "https://worker.internal.example" not in rendered
    assert "secret-value" not in rendered
    assert "https://www.googleapis.com/auth/gmail.readonly" not in rendered


def test_operator_input_request_cli_writes_report(tmp_path: Path, capsys) -> None:
    receipt_path = _write_blocked_binding_receipt(tmp_path)
    output_path = tmp_path / "operator_input_request.json"
    request = emit_finance_email_calendar_operator_input_request(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_finance_email_calendar_operator_input_request(request, output_path)
    exit_code = main(
        [
            "--receipt",
            str(receipt_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["handoff_allowed"] is False
    assert payload["required_inputs"]
    assert stdout_payload["next_action"] == payload["next_action"]
    assert captured.err == ""


def test_operator_input_request_allows_ready_binding_receipt(tmp_path: Path) -> None:
    receipt_path = _write_ready_binding_receipt(tmp_path)

    request = emit_finance_email_calendar_operator_input_request(
        receipt_path=receipt_path,
        schema_path=SCHEMA_PATH,
    )

    assert request.ready is True
    assert request.handoff_allowed is True
    assert request.solver_outcome == "SolvedVerified"
    assert request.proof_state == "Pass"
    assert request.required_inputs == ()
    assert request.blocked_actions == ()


def _write_blocked_binding_receipt(tmp_path: Path) -> Path:
    receipt_path = tmp_path / "finance_approval_email_calendar_binding_receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "receipt_id": "finance-email-calendar-binding-receipt-0123456789abcdef",
                "ready": False,
                "readiness_blockers": [
                    "missing_worker_endpoint",
                    "missing_worker_secret",
                    "missing_connector_token",
                    "missing_read_only_scope_witness",
                ],
                "debug_values_not_expected": [
                    "https://worker.internal.example",
                    "secret-value",
                    "https://www.googleapis.com/auth/gmail.readonly",
                ],
            }
        ),
        encoding="utf-8",
    )
    return receipt_path


def _write_ready_binding_receipt(tmp_path: Path) -> Path:
    receipt_path = tmp_path / "finance_approval_email_calendar_binding_receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "receipt_id": "finance-email-calendar-binding-receipt-fedcba9876543210",
                "ready": True,
                "readiness_blockers": [],
            }
        ),
        encoding="utf-8",
    )
    return receipt_path
