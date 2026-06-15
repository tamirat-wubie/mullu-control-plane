"""Tests for durable Gmail account-binding operator input requests.

Purpose: prove Gmail account-binding evidence remains blocked until runtime
token, expected hash, hash salt, tenant ref, and source live receipt inputs are
explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.emit_durable_gmail_account_binding_operator_input_request
and scripts.validate_durable_gmail_account_binding_operator_input_request.
Invariants:
  - Missing inputs are public-safe and redacted.
  - Completed input packets still do not authorize Gmail profile probes or
    account-binding claims.
  - Overclaims, path traversal, raw mailbox addresses, and secret markers are blocked.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_durable_gmail_account_binding_operator_input_request import (
    REQUIRED_BLOCKED_ACTIONS,
    emit_durable_gmail_account_binding_operator_input_request,
    main as emit_main,
    write_durable_gmail_account_binding_operator_input_request,
)
from scripts.validate_durable_gmail_account_binding_operator_input_request import (
    validate_durable_gmail_account_binding_operator_input_request,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "durable_gmail_account_binding_operator_input_request.schema.json"


def test_account_binding_operator_input_request_reports_missing_inputs() -> None:
    request = emit_durable_gmail_account_binding_operator_input_request(
        environment={},
        schema_path=SCHEMA_PATH,
    )
    input_kinds = {item.input_kind for item in request.required_inputs}

    assert request.request_id.startswith("durable-gmail-account-binding-input-request-")
    assert request.ready_for_operator_review is False
    assert request.profile_probe_allowed is False
    assert request.account_binding_claim_allowed is False
    assert request.solver_outcome == "AwaitingEvidence"
    assert request.proof_state == "Unknown"
    assert {
        "access_token_runtime_binding",
        "expected_account_hash_binding",
        "hash_salt_runtime_binding",
        "tenant_ref_binding",
        "source_live_receipt_ref",
    } <= input_kinds
    assert set(request.blocked_actions) == set(REQUIRED_BLOCKED_ACTIONS)
    assert request.no_secret_values_serialized is True
    assert request.external_provider_call_performed is False
    assert request.provider_mutation_performed is False


def test_account_binding_operator_input_request_ready_for_review_still_blocks_binding() -> None:
    request = emit_durable_gmail_account_binding_operator_input_request(
        environment=_ready_env(),
        schema_path=SCHEMA_PATH,
    )

    assert request.ready_for_operator_review is True
    assert request.profile_probe_allowed is False
    assert request.account_binding_claim_allowed is False
    assert request.solver_outcome == "SolvedVerified"
    assert request.proof_state == "Pass"
    assert request.required_inputs == ()
    assert "gmail_profile_probe" in request.blocked_actions
    assert "account_binding_claim" in request.blocked_actions
    assert request.account_binding_summary["profile_probe_required"] is True
    assert request.external_provider_call_performed is False
    assert request.source_artifacts["source_live_receipt_ref"] == (
        ".change_assurance/durable_gmail_oauth_live_receipt.json"
    )


def test_account_binding_operator_input_request_redacts_invalid_secret_and_mailbox_refs() -> None:
    env = dict(_ready_env())
    env["MULLU_GMAIL_ACCOUNT_BINDING_TENANT_REF"] = "tenant://operator@example.com"
    env["MULLU_GMAIL_ACCOUNT_BINDING_SOURCE_RECEIPT_REF"] = "client_secret=raw-secret"

    request = emit_durable_gmail_account_binding_operator_input_request(
        environment=env,
        schema_path=SCHEMA_PATH,
    )
    serialized = json.dumps(request.as_dict(), sort_keys=True)
    input_kinds = {item.input_kind for item in request.required_inputs}

    assert request.ready_for_operator_review is False
    assert "valid_tenant_ref_binding" in input_kinds
    assert "valid_source_live_receipt_ref" in input_kinds
    assert "operator@example.com" not in serialized
    assert "raw-secret" not in serialized
    assert request.source_artifacts["source_live_receipt_ref"] == ""


def test_account_binding_operator_input_request_flags_invalid_expected_hash() -> None:
    env = dict(_ready_env())
    env["MULLU_GMAIL_EXPECTED_ACCOUNT_HASH"] = "ABC123"

    request = emit_durable_gmail_account_binding_operator_input_request(
        environment=env,
        schema_path=SCHEMA_PATH,
    )
    input_kinds = {item.input_kind for item in request.required_inputs}

    assert request.ready_for_operator_review is False
    assert "valid_expected_account_hash_binding" in input_kinds
    assert request.raw_hash_material_disclosed is False


def test_account_binding_operator_input_request_validator_blocks_overclaims(tmp_path: Path) -> None:
    request_path = tmp_path / "durable_gmail_account_binding_operator_input_request.json"
    request = emit_durable_gmail_account_binding_operator_input_request(
        environment=_ready_env(),
        schema_path=SCHEMA_PATH,
    ).as_dict()
    request["profile_probe_allowed"] = True
    request["account_binding_claim_allowed"] = True
    request["external_provider_call_performed"] = True
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation = validate_durable_gmail_account_binding_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    assert validation.valid is False
    assert validation.profile_probe_allowed is True
    assert validation.account_binding_claim_allowed is True
    assert any("profile_probe_allowed" in error for error in validation.errors)
    assert any("account_binding_claim_allowed" in error for error in validation.errors)
    assert any("external_provider_call_performed" in error for error in validation.errors)


def test_account_binding_operator_input_request_validator_rejects_traversal_ref(tmp_path: Path) -> None:
    request_path = tmp_path / "durable_gmail_account_binding_operator_input_request.json"
    request = emit_durable_gmail_account_binding_operator_input_request(
        environment=_ready_env(),
        schema_path=SCHEMA_PATH,
    ).as_dict()
    request["source_artifacts"]["source_live_receipt_ref"] = "../secret/account.json"
    request["ready_for_operator_review"] = True
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation = validate_durable_gmail_account_binding_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready_for_operator_review is True
    assert any("ready_for_operator_review" in error for error in validation.errors)


def test_account_binding_operator_input_request_cli_writes_and_validates(tmp_path: Path, monkeypatch, capsys) -> None:
    output_path = tmp_path / "durable_gmail_account_binding_operator_input_request.json"
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
    validation = validate_durable_gmail_account_binding_operator_input_request(
        request_path=output_path,
        schema_path=SCHEMA_PATH,
        require_ready_for_operator_review=True,
        require_blocked=True,
    )

    assert exit_code == 0
    assert payload["ready_for_operator_review"] is True
    assert payload["profile_probe_allowed"] is False
    assert payload["account_binding_claim_allowed"] is False
    assert stdout_payload["request_id"] == payload["request_id"]
    assert validation.valid is True
    assert captured.err == ""


def test_account_binding_operator_input_request_writer_returns_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "request.json"
    request = emit_durable_gmail_account_binding_operator_input_request(
        environment={},
        schema_path=SCHEMA_PATH,
    )

    written = write_durable_gmail_account_binding_operator_input_request(request, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert payload["ready_for_operator_review"] is False
    assert payload["required_inputs"]


def _ready_env() -> dict[str, str]:
    return {
        "GMAIL_ACCESS_TOKEN": "runtime-access-token",
        "MULLU_GMAIL_EXPECTED_ACCOUNT_HASH": "a" * 64,
        "GMAIL_ACCOUNT_BINDING_HASH_SALT": "runtime-hash-salt",
        "MULLU_GMAIL_ACCOUNT_BINDING_TENANT_REF": "tenant://mullusi-foundation",
        "MULLU_GMAIL_ACCOUNT_BINDING_SOURCE_RECEIPT_REF": (
            ".change_assurance/durable_gmail_oauth_live_receipt.json"
        ),
    }
