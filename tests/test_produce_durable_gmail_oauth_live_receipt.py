"""Tests for durable Gmail OAuth live receipt production.

Purpose: prove refresh-token based Gmail evidence stays redacted while feeding
the existing read-only email/calendar live probe.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.produce_durable_gmail_oauth_live_receipt.
Invariants:
  - Refresh and access token values are never serialized.
  - Preflight blocks provider calls when evidence is incomplete.
  - Successful refresh invokes the Gmail live receipt producer with a transient token.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping

from scripts.produce_capability_adapter_live_receipts import LiveReceiptWrite
from scripts.produce_durable_gmail_oauth_live_receipt import (
    TokenRefreshExchange,
    produce_durable_gmail_oauth_live_receipt,
)


def _ready_env() -> dict[str, str]:
    return {
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER": "production",
        "EMAIL_CALENDAR_CONNECTOR_ID": "gmail",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_only_search",
        "GMAIL_SCOPE_ID": "https://www.googleapis.com/auth/gmail.readonly",
        "GMAIL_OAUTH_CLIENT_ID": "client-id-secret-shaped-value",
        "GMAIL_OAUTH_CLIENT_SECRET": "client-secret-value",
        "GMAIL_REFRESH_TOKEN": "refresh-token-value",
        "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF": "witness:gmail-consent",
        "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF": "witness:gmail-client",
        "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF": "receipt:gmail-scope",
        "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF": "receipt:gmail-refresh-storage",
        "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF": "receipt:gmail-revocation-recovery",
    }


@dataclass(slots=True)
class _ProbeCall:
    output_path: Path
    connector_id: str
    query: str
    gmail_access_token_present: bool


def test_successful_refresh_runs_live_probe_without_serializing_tokens(tmp_path: Path) -> None:
    calls: list[_ProbeCall] = []

    def refresh_exchange(endpoint: str, form: Mapping[str, str], timeout: int) -> TokenRefreshExchange:
        assert endpoint == "https://oauth2.googleapis.com/token"
        assert form["grant_type"] == "refresh_token"
        assert form["refresh_token"] == "refresh-token-value"
        assert timeout == 20
        return TokenRefreshExchange(
            status_code=200,
            response_payload={
                "access_token": "ya29.runtime-token-value",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
            access_token="ya29.runtime-token-value",
        )

    def produce_email_receipt(**kwargs: Any) -> LiveReceiptWrite:
        calls.append(
            _ProbeCall(
                output_path=kwargs["output_path"],
                connector_id=kwargs["connector_id"],
                query=kwargs["query"],
                gmail_access_token_present=bool(os.environ.get("GMAIL_ACCESS_TOKEN")),
            )
        )
        return LiveReceiptWrite(
            adapter_id="communication.email_calendar_worker",
            status="passed",
            output_path=str(kwargs["output_path"]),
            blockers=(),
        )

    output_path = tmp_path / "durable.json"
    email_output_path = tmp_path / "email.json"
    payload = produce_durable_gmail_oauth_live_receipt(
        environment=_ready_env(),
        output_path=output_path,
        email_calendar_output_path=email_output_path,
        query="newer_than:1d",
        clock=lambda: "2026-06-12T00:00:00Z",
        refresh_exchange=refresh_exchange,
        email_calendar_receipt_producer=produce_email_receipt,
    )
    serialized = output_path.read_text(encoding="utf-8")

    assert payload["status"] == "passed"
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["external_mailbox_write_performed"] is False
    assert payload["refresh_outcome"]["status"] == "refreshed"
    assert calls == [_ProbeCall(email_output_path, "gmail", "newer_than:1d", True)]
    assert "ya29.runtime-token-value" not in serialized
    assert "refresh-token-value" not in serialized
    assert "client-secret-value" not in serialized


def test_preflight_blocks_refresh_when_witnesses_are_missing(tmp_path: Path) -> None:
    called = False

    def refresh_exchange(endpoint: str, form: Mapping[str, str], timeout: int) -> TokenRefreshExchange:
        nonlocal called
        called = True
        return TokenRefreshExchange(status_code=503, response_payload={}, access_token="")

    environment = _ready_env()
    environment["MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF"] = ""
    payload = produce_durable_gmail_oauth_live_receipt(
        environment=environment,
        output_path=tmp_path / "durable.json",
        email_calendar_output_path=tmp_path / "email.json",
        refresh_exchange=refresh_exchange,
    )

    assert called is False
    assert payload["status"] == "failed"
    assert payload["solver_outcome"] == "AwaitingEvidence"
    assert payload["external_provider_call_performed"] is False
    assert "gmail_oauth_preflight_not_ready" in payload["blockers"]


def test_failed_refresh_emits_recovery_without_running_probe(tmp_path: Path) -> None:
    def refresh_exchange(endpoint: str, form: Mapping[str, str], timeout: int) -> TokenRefreshExchange:
        return TokenRefreshExchange(
            status_code=400,
            response_payload={"error": "invalid_grant"},
            access_token="",
        )

    def produce_email_receipt(**kwargs: Any) -> LiveReceiptWrite:
        raise AssertionError("live probe must not run after failed refresh")

    payload = produce_durable_gmail_oauth_live_receipt(
        environment=_ready_env(),
        output_path=tmp_path / "durable.json",
        email_calendar_output_path=tmp_path / "email.json",
        refresh_exchange=refresh_exchange,
        email_calendar_receipt_producer=produce_email_receipt,
    )
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["status"] == "failed"
    assert payload["refresh_outcome"]["status"] == "refresh_token_revoked_or_expired"
    assert payload["refresh_outcome"]["requires_reauthorization"] is True
    assert "gmail_oauth_refresh_failed:refresh_token_revoked_or_expired" in payload["blockers"]
    assert "refresh-token-value" not in serialized
