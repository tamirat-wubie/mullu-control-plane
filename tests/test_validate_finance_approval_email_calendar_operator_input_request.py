"""Tests for finance email/calendar operator input request validation.

Purpose: prove operator input requests are schema-backed and semantically
checked before operators rely on them.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_finance_approval_email_calendar_operator_input_request.
Invariants:
  - Handoff allowance matches readiness and missing inputs.
  - Blocked requests preserve required inputs and blocked actions.
  - Validation reports remain public-safe.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_finance_approval_email_calendar_operator_input_request import (  # noqa: E402
    main,
    validate_finance_email_calendar_operator_input_request,
    write_finance_email_calendar_operator_input_request_validation,
)

SCHEMA_PATH = _ROOT / "schemas" / "finance_approval_email_calendar_operator_input_request.schema.json"


def test_validate_operator_input_request_accepts_blocked_request(tmp_path: Path) -> None:
    request_path = tmp_path / "finance_email_calendar_operator_input_request.json"
    request_path.write_text(json.dumps(_blocked_request()), encoding="utf-8")

    validation = validate_finance_email_calendar_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    assert validation.valid is True
    assert validation.handoff_allowed is False
    assert validation.errors == ()
    assert validation.next_action == "bind worker endpoint"
    assert validation.request_path == "finance_email_calendar_operator_input_request.json"


def test_validate_operator_input_request_rejects_handoff_drift(tmp_path: Path) -> None:
    request_path = tmp_path / "finance_email_calendar_operator_input_request.json"
    payload = _blocked_request()
    payload["handoff_allowed"] = True
    request_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_finance_email_calendar_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert any("handoff_allowed must equal" in error for error in validation.errors)


def test_validate_operator_input_request_rejects_ready_drift(tmp_path: Path) -> None:
    request_path = tmp_path / "finance_email_calendar_operator_input_request.json"
    payload = _ready_request()
    payload["blocked_actions"] = ["email_calendar_live_probe"]
    request_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_finance_email_calendar_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert any("handoff_allowed must equal" in error for error in validation.errors)


def test_validate_operator_input_request_cli_writes_report(tmp_path: Path, capsys) -> None:
    request_path = tmp_path / "finance_email_calendar_operator_input_request.json"
    output_path = tmp_path / "finance_email_calendar_operator_input_request_validation.json"
    request_path.write_text(json.dumps(_blocked_request()), encoding="utf-8")
    validation = validate_finance_email_calendar_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    written = write_finance_email_calendar_operator_input_request_validation(
        validation,
        output_path,
    )
    exit_code = main(
        [
            "--request",
            str(request_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--require-blocked",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["handoff_allowed"] is False
    assert stdout_payload["next_action"] == "bind worker endpoint"
    assert captured.err == ""


def _blocked_request() -> dict[str, object]:
    return {
        "request_id": "finance-email-calendar-operator-input-request-0123456789abcdef",
        "receipt_id": "finance-email-calendar-binding-receipt-0123456789abcdef",
        "ready": False,
        "handoff_allowed": False,
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "required_inputs": [
            {
                "input_id": "finance-email-calendar-input-0123456789ab",
                "blocker": "missing_worker_endpoint",
                "input_kind": "worker_endpoint",
                "required_names": ["MULLU_EMAIL_CALENDAR_WORKER_URL"],
                "current_state": "missing",
                "evidence_source": "finance_approval_email_calendar_binding_receipt",
                "next_action": "bind worker endpoint",
            }
        ],
        "blocked_actions": [
            "email_calendar_live_probe",
            "finance_approval_live_handoff",
            "customer_or_external_email_dispatch",
            "finance_approval_production_readiness_claim",
        ],
        "source_artifacts": {
            "finance_approval_email_calendar_binding_receipt": "D:/packet/finance_binding_receipt.json"
        },
        "no_secret_values_serialized": True,
        "next_action": "bind worker endpoint",
    }


def _ready_request() -> dict[str, object]:
    return {
        "request_id": "finance-email-calendar-operator-input-request-fedcba9876543210",
        "receipt_id": "finance-email-calendar-binding-receipt-fedcba9876543210",
        "ready": True,
        "handoff_allowed": True,
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "required_inputs": [],
        "blocked_actions": [],
        "source_artifacts": {
            "finance_approval_email_calendar_binding_receipt": "D:/packet/finance_binding_receipt.json"
        },
        "no_secret_values_serialized": True,
        "next_action": "run finance email/calendar live receipt probe with require-ready validation",
    }
