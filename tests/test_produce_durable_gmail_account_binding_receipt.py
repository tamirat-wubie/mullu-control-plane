"""Tests for durable Gmail account binding receipt production.

Purpose: prove the Gmail profile-probe producer writes only redacted account
binding evidence and fails closed on missing input, profile errors, or hash
mismatch.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.produce_durable_gmail_account_binding_receipt.
Invariants:
  - Access token, raw mailbox address, and salt values are never serialized.
  - Provider profile probing is read-only.
  - Account hash mismatch blocks tenant binding.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.produce_durable_gmail_account_binding_receipt import (
    GmailProfileProbe,
    produce_account_binding_receipt,
)
from scripts.validate_durable_gmail_account_binding_receipt import validate_account_binding_receipt


MAILBOX_ADDRESS = "operator@example.com"
HASH_SALT = "local-secret-salt"


def _account_hash(mailbox_address: str = MAILBOX_ADDRESS) -> str:
    return hashlib.sha256(f"{HASH_SALT}:{mailbox_address.strip().lower()}".encode("utf-8")).hexdigest()


def _ready_env() -> dict[str, str]:
    return {
        "GMAIL_ACCESS_TOKEN": "runtime-access-token",
        "MULLU_GMAIL_EXPECTED_ACCOUNT_HASH": _account_hash(),
        "GMAIL_ACCOUNT_BINDING_HASH_SALT": HASH_SALT,
        "MULLU_GMAIL_ACCOUNT_BINDING_HASH_SALT_REF": "secret:GMAIL_ACCOUNT_BINDING_HASH_SALT",
        "MULLU_GMAIL_ACCOUNT_BINDING_TENANT_REF": "tenant://mullusi-foundation",
        "MULLU_GMAIL_ACCOUNT_BINDING_SOURCE_RECEIPT_REF": ".change_assurance/durable_gmail_oauth_live_receipt.json",
    }


def test_successful_profile_probe_writes_redacted_binding_receipt(tmp_path: Path) -> None:
    calls: list[tuple[str, str, int]] = []

    def profile_probe(endpoint: str, access_token: str, timeout_seconds: int) -> GmailProfileProbe:
        calls.append((endpoint, access_token, timeout_seconds))
        return GmailProfileProbe(
            status_code=200,
            response_payload={"emailAddress": MAILBOX_ADDRESS},
            email_address=MAILBOX_ADDRESS,
        )

    output_path = tmp_path / "binding.json"
    payload = produce_account_binding_receipt(
        environment=_ready_env(),
        output_path=output_path,
        clock=lambda: "2026-06-13T00:00:00Z",
        profile_probe=profile_probe,
    )
    serialized = output_path.read_text(encoding="utf-8")
    validation = validate_account_binding_receipt(
        output_path,
        now="2026-06-13T00:00:00Z",
        require_source_fresh=False,
    )

    assert payload["status"] == "passed"
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["observed_account_hash"] == _account_hash()
    assert payload["external_mailbox_write_performed"] is False
    assert validation["ready_for_tenant_binding"] is True
    assert calls == [("https://gmail.googleapis.com/gmail/v1/users/me/profile", "runtime-access-token", 20)]
    assert MAILBOX_ADDRESS not in serialized
    assert HASH_SALT not in serialized
    assert "runtime-access-token" not in serialized


def test_missing_inputs_block_without_provider_call(tmp_path: Path) -> None:
    called = False

    def profile_probe(endpoint: str, access_token: str, timeout_seconds: int) -> GmailProfileProbe:
        nonlocal called
        called = True
        return GmailProfileProbe(status_code=200, response_payload={}, email_address=MAILBOX_ADDRESS)

    environment = _ready_env()
    environment["MULLU_GMAIL_EXPECTED_ACCOUNT_HASH"] = ""
    payload = produce_account_binding_receipt(
        environment=environment,
        output_path=tmp_path / "binding.json",
        profile_probe=profile_probe,
    )

    assert called is False
    assert payload["status"] == "failed"
    assert payload["external_provider_call_performed"] is False
    assert "mullu_gmail_expected_account_hash_missing" in payload["blockers"]
    assert payload["observed_account_hash"] == ""


def test_invalid_timeout_blocks_without_provider_call(tmp_path: Path) -> None:
    called = False

    def profile_probe(endpoint: str, access_token: str, timeout_seconds: int) -> GmailProfileProbe:
        nonlocal called
        called = True
        return GmailProfileProbe(status_code=200, response_payload={}, email_address=MAILBOX_ADDRESS)

    payload = produce_account_binding_receipt(
        environment=_ready_env(),
        output_path=tmp_path / "binding.json",
        timeout_seconds=0,
        profile_probe=profile_probe,
    )

    assert called is False
    assert payload["status"] == "failed"
    assert payload["external_provider_call_performed"] is False
    assert "timeout_seconds_invalid" in payload["blockers"]


def test_profile_probe_failure_blocks_binding(tmp_path: Path) -> None:
    def profile_probe(endpoint: str, access_token: str, timeout_seconds: int) -> GmailProfileProbe:
        return GmailProfileProbe(
            status_code=401,
            response_payload={"error": "unauthorized"},
            email_address="",
        )

    payload = produce_account_binding_receipt(
        environment=_ready_env(),
        output_path=tmp_path / "binding.json",
        clock=lambda: "2026-06-13T00:00:00Z",
        profile_probe=profile_probe,
    )
    validation = validate_account_binding_receipt(
        tmp_path / "binding.json",
        now="2026-06-13T00:00:00Z",
        require_source_fresh=False,
    )

    assert payload["status"] == "failed"
    assert payload["solver_outcome"] == "AwaitingEvidence"
    assert "gmail_profile_probe_failed" in payload["blockers"]
    assert validation["ready_for_tenant_binding"] is False
    assert "account_binding_not_passing" in validation["blockers"]


def test_hash_mismatch_blocks_binding_without_address_disclosure(tmp_path: Path) -> None:
    def profile_probe(endpoint: str, access_token: str, timeout_seconds: int) -> GmailProfileProbe:
        return GmailProfileProbe(
            status_code=200,
            response_payload={"emailAddress": "wrong@example.com"},
            email_address="wrong@example.com",
        )

    output_path = tmp_path / "binding.json"
    payload = produce_account_binding_receipt(
        environment=_ready_env(),
        output_path=output_path,
        clock=lambda: "2026-06-13T00:00:00Z",
        profile_probe=profile_probe,
    )
    serialized = json.dumps(payload, sort_keys=True)
    validation = validate_account_binding_receipt(
        output_path,
        now="2026-06-13T00:00:00Z",
        require_source_fresh=False,
    )

    assert payload["status"] == "failed"
    assert payload["observed_account_hash"] != payload["expected_account_hash"]
    assert "account_hash_mismatch" in payload["blockers"]
    assert validation["ready_for_tenant_binding"] is False
    assert "wrong@example.com" not in serialized
    assert "operator@example.com" not in output_path.read_text(encoding="utf-8")
