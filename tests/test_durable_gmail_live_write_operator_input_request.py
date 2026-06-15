"""Tests for durable Gmail live write operator input requests.

Purpose: prove Gmail live write evidence remains blocked until account binding,
source live, write rehearsal, approval, and scope inputs are explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.emit_durable_gmail_live_write_operator_input_request
and scripts.validate_durable_gmail_live_write_operator_input_request.
Invariants:
  - Missing inputs are public-safe and redacted.
  - Completed input packets still do not authorize Gmail draft or send.
  - Overclaims, path traversal, raw mailbox addresses, and secret markers are blocked.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_durable_gmail_live_write_operator_input_request import (
    REQUIRED_BLOCKED_ACTIONS,
    emit_durable_gmail_live_write_operator_input_request,
    main as emit_main,
    write_durable_gmail_live_write_operator_input_request,
)
from scripts.validate_durable_gmail_live_write_operator_input_request import (
    validate_durable_gmail_live_write_operator_input_request,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "durable_gmail_live_write_operator_input_request.schema.json"


def test_live_write_operator_input_request_reports_missing_inputs() -> None:
    request = emit_durable_gmail_live_write_operator_input_request(
        environment={},
        schema_path=SCHEMA_PATH,
    )
    input_kinds = {item.input_kind for item in request.required_inputs}

    assert request.request_id.startswith("durable-gmail-live-write-input-request-")
    assert request.ready_for_operator_review is False
    assert request.write_action_allowed is False
    assert request.solver_outcome == "AwaitingEvidence"
    assert request.proof_state == "Unknown"
    assert {
        "account_binding_receipt_ref",
        "source_live_receipt_ref",
        "write_rehearsal_receipt_ref",
        "write_approval_receipt_ref",
        "gmail_scope_binding",
    } <= input_kinds
    assert set(request.blocked_actions) == set(REQUIRED_BLOCKED_ACTIONS)
    assert request.no_secret_values_serialized is True
    assert request.external_provider_call_performed is False
    assert request.external_send_performed is False


def test_live_write_operator_input_request_ready_for_review_still_blocks_write() -> None:
    request = emit_durable_gmail_live_write_operator_input_request(
        environment=_ready_env(),
        schema_path=SCHEMA_PATH,
    )

    assert request.ready_for_operator_review is True
    assert request.write_action_allowed is False
    assert request.solver_outcome == "SolvedVerified"
    assert request.proof_state == "Pass"
    assert request.required_inputs == ()
    assert "gmail_live_send" in request.blocked_actions
    assert "gmail_write_authority_claim" in request.blocked_actions
    assert request.operation_summary["required_scope_ref"] == "oauth:gmail.send"
    assert request.external_draft_created is False
    assert request.external_send_performed is False


def test_live_write_operator_input_request_supports_draft_scope() -> None:
    env = dict(_ready_env())
    env["MULLU_GMAIL_WRITE_OPERATION_FAMILY"] = "draft_create"
    env["GMAIL_SCOPE_ID"] = "https://www.googleapis.com/auth/gmail.compose"

    request = emit_durable_gmail_live_write_operator_input_request(
        environment=env,
        schema_path=SCHEMA_PATH,
    )

    assert request.operation_family == "draft_create"
    assert request.ready_for_operator_review is True
    assert request.operation_summary["required_scope_ref"] == "oauth:gmail.compose"


def test_live_write_operator_input_request_blocks_unsupported_operation() -> None:
    env = dict(_ready_env())
    env["MULLU_GMAIL_WRITE_OPERATION_FAMILY"] = "send_without_approval"

    request = emit_durable_gmail_live_write_operator_input_request(
        environment=env,
        schema_path=SCHEMA_PATH,
    )

    assert request.ready_for_operator_review is False
    assert request.solver_outcome == "GovernanceBlocked"
    assert request.proof_state == "Fail"
    assert request.required_inputs[0].input_kind == "valid_operation_family"
    assert request.write_action_allowed is False


def test_live_write_operator_input_request_redacts_invalid_secret_and_mailbox_refs() -> None:
    env = dict(_ready_env())
    env["MULLU_GMAIL_WRITE_APPROVAL_RECEIPT_REF"] = "approval:operator@example.com"
    env["MULLU_GMAIL_WRITE_REHEARSAL_RECEIPT_REF"] = "client_secret=raw-secret"

    request = emit_durable_gmail_live_write_operator_input_request(
        environment=env,
        schema_path=SCHEMA_PATH,
    )
    serialized = json.dumps(request.as_dict(), sort_keys=True)
    input_kinds = {item.input_kind for item in request.required_inputs}

    assert request.ready_for_operator_review is False
    assert "valid_write_approval_receipt_ref" in input_kinds
    assert "valid_write_rehearsal_receipt_ref" in input_kinds
    assert "operator@example.com" not in serialized
    assert "raw-secret" not in serialized
    assert request.source_artifacts["write_approval_receipt_ref"] == ""
    assert request.source_artifacts["write_rehearsal_receipt_ref"] == ""


def test_live_write_operator_input_request_validator_blocks_overclaims(tmp_path: Path) -> None:
    request_path = tmp_path / "durable_gmail_live_write_operator_input_request.json"
    request = emit_durable_gmail_live_write_operator_input_request(
        environment=_ready_env(),
        schema_path=SCHEMA_PATH,
    ).as_dict()
    request["write_action_allowed"] = True
    request["external_send_performed"] = True
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation = validate_durable_gmail_live_write_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.write_action_allowed is True
    assert any("write_action_allowed" in error for error in validation.errors)
    assert any("external_send_performed" in error for error in validation.errors)


def test_live_write_operator_input_request_validator_rejects_traversal_ref(tmp_path: Path) -> None:
    request_path = tmp_path / "durable_gmail_live_write_operator_input_request.json"
    request = emit_durable_gmail_live_write_operator_input_request(
        environment=_ready_env(),
        schema_path=SCHEMA_PATH,
    ).as_dict()
    request["source_artifacts"]["account_binding_receipt_ref"] = "../secret/account.json"
    request["ready_for_operator_review"] = True
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation = validate_durable_gmail_live_write_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready_for_operator_review is True
    assert any("ready_for_operator_review" in error for error in validation.errors)


def test_live_write_operator_input_request_cli_writes_and_validates(tmp_path: Path, monkeypatch, capsys) -> None:
    output_path = tmp_path / "durable_gmail_live_write_operator_input_request.json"
    for key, value in _ready_env().items():
        monkeypatch.setenv(key, value)

    exit_code = emit_main(
        [
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
    validation = validate_durable_gmail_live_write_operator_input_request(
        request_path=output_path,
        schema_path=SCHEMA_PATH,
        require_ready_for_operator_review=True,
        require_blocked=True,
    )

    assert exit_code == 0
    assert payload["ready_for_operator_review"] is True
    assert payload["write_action_allowed"] is False
    assert stdout_payload["request_id"] == payload["request_id"]
    assert validation.valid is True
    assert captured.err == ""


def test_live_write_operator_input_request_writer_returns_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "request.json"
    request = emit_durable_gmail_live_write_operator_input_request(
        environment={},
        schema_path=SCHEMA_PATH,
    )

    written = write_durable_gmail_live_write_operator_input_request(request, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert payload["ready_for_operator_review"] is False
    assert payload["required_inputs"]


def _ready_env() -> dict[str, str]:
    return {
        "MULLU_GMAIL_ACCOUNT_BINDING_RECEIPT_REF": ".change_assurance/durable_gmail_account_binding_receipt.json",
        "MULLU_GMAIL_WRITE_SOURCE_LIVE_RECEIPT_REF": ".change_assurance/durable_gmail_oauth_live_receipt.json",
        "MULLU_GMAIL_WRITE_REHEARSAL_RECEIPT_REF": ".change_assurance/durable_gmail_write_authority_rehearsal_receipt.json",
        "MULLU_GMAIL_WRITE_APPROVAL_RECEIPT_REF": "approval:gmail-live-write-20260614",
        "MULLU_GMAIL_WRITE_OPERATION_FAMILY": "send_with_approval",
        "GMAIL_SCOPE_ID": "https://www.googleapis.com/auth/gmail.send",
    }
