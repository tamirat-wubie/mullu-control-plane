"""Gateway GitHub App token-exchange receipt tests.

Purpose: verify token-exchange planning is hash-bound, schema-backed, and
non-live unless an external GitHub App exchange receipt is bound.
Governance scope: repository identity, app installation boundary, private-key
fingerprint, requested permissions, TTL, response evidence, and secret absence.
Dependencies: gateway.github_app_token_exchange and token-exchange schema.
Invariants:
  - Plan-only and dry-run modes do not call GitHub or mint tokens.
  - Exchange-approved mode requires external execution evidence.
  - Raw tokens, JWTs, and private keys are never accepted as receipt evidence.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

import pytest

from gateway.github_app_token_exchange import (
    GitHubAppTokenExchange,
    GitHubAppTokenExchangeRequest,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "github_app_token_exchange_receipt.schema.json"
HEX_DIGITS = set("0123456789abcdef")
PRIVATE_KEY_FINGERPRINT = "sha256:" + ("a" * 64)
TOKEN_FINGERPRINT = "sha256:" + ("b" * 64)
RESPONSE_HASH = "sha256:" + ("c" * 64)


def test_github_app_token_exchange_plan_only_builds_hash_bound_payload() -> None:
    receipt = GitHubAppTokenExchange().evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "planned"
    assert receipt.mode == "plan_only"
    assert receipt.endpoint == "/app/installations/67890/access_tokens"
    assert receipt.method == "POST"
    assert receipt.request_payload["repositories"] == ["mullu-control-plane"]
    assert receipt.request_payload["permissions"]["checks"] == "write"
    assert receipt.request_payload["ttl_seconds"] == 3600
    assert len(receipt.request_payload_hash) == 64
    assert set(receipt.request_payload_hash) <= HEX_DIGITS
    assert len(receipt.receipt_hash) == 64
    assert set(receipt.receipt_hash) <= HEX_DIGITS
    assert receipt.external_token_exchange_admitted is False
    assert receipt.network_call_performed is False
    assert receipt.private_key_loaded is False
    assert receipt.jwt_created is False
    assert receipt.raw_token_stored is False
    assert receipt.metadata["payload_hash_bound"] is True


def test_github_app_token_exchange_dry_run_rejects_response_evidence() -> None:
    receipt = GitHubAppTokenExchange().evaluate(
        replace(
            _request(mode="dry_run"),
            approval_ref="approval://github-app-token/exchange-1",
            execution_receipt_ref="receipt://github-app/token-exchange-1",
            response_status_code=201,
            token_fingerprint=TOKEN_FINGERPRINT,
            token_expires_at="2026-06-15T16:00:00Z",
            response_payload_hash=RESPONSE_HASH,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "non_exchange_approval_ref_forbidden" in receipt.blocked_reasons
    assert "non_exchange_execution_receipt_forbidden" in receipt.blocked_reasons
    assert "non_exchange_response_status_forbidden" in receipt.blocked_reasons
    assert "non_exchange_token_fingerprint_forbidden" in receipt.blocked_reasons
    assert "non_exchange_token_expiry_forbidden" in receipt.blocked_reasons
    assert "non_exchange_response_payload_hash_forbidden" in receipt.blocked_reasons
    assert receipt.external_token_exchange_admitted is False
    assert receipt.metadata["github_api_not_called"] is True


def test_github_app_token_exchange_approved_requires_external_receipt() -> None:
    receipt = GitHubAppTokenExchange().evaluate(_request(mode="exchange_approved"))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "approval_ref_required" in receipt.blocked_reasons
    assert "execution_receipt_ref_required" in receipt.blocked_reasons
    assert "response_status_code_2xx_required" in receipt.blocked_reasons
    assert "token_fingerprint_required" in receipt.blocked_reasons
    assert "token_expires_at_required" in receipt.blocked_reasons
    assert "response_payload_hash_required" in receipt.blocked_reasons
    assert "github_app_external_exchange_receipt" in receipt.required_controls
    assert receipt.external_token_exchange_admitted is False


def test_github_app_token_exchange_approved_binds_external_receipt() -> None:
    receipt = GitHubAppTokenExchange().evaluate(
        replace(
            _request(mode="exchange_approved"),
            approval_ref="approval://github-app-token/exchange-1",
            execution_receipt_ref="receipt://github-app/token-exchange-1",
            response_status_code=201,
            token_fingerprint=TOKEN_FINGERPRINT,
            token_expires_at="2026-06-15T16:00:00Z",
            response_payload_hash=RESPONSE_HASH,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "exchange_receipt_bound"
    assert receipt.external_token_exchange_admitted is True
    assert receipt.approval_ref == "approval://github-app-token/exchange-1"
    assert receipt.execution_receipt_ref == "receipt://github-app/token-exchange-1"
    assert receipt.response_status_code == 201
    assert receipt.token_fingerprint == TOKEN_FINGERPRINT
    assert receipt.token_expires_at == "2026-06-15T16:00:00Z"
    assert receipt.response_payload_hash == RESPONSE_HASH
    assert receipt.blocked_reasons == []
    assert receipt.network_call_performed is False
    assert receipt.private_key_loaded is False
    assert receipt.jwt_created is False
    assert receipt.raw_token_stored is False
    assert receipt.metadata["external_token_exchange_admitted"] is True


def test_github_app_token_exchange_rejects_raw_token_disclosure() -> None:
    receipt = GitHubAppTokenExchange().evaluate(
        replace(
            _request(),
            metadata={"debug_installation_token": "ghs_" + ("a" * 32)},
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "secret_values_disclosed" in receipt.blocked_reasons
    assert receipt.metadata["secret_absence_verified"] is False
    assert receipt.external_token_exchange_admitted is False
    assert receipt.raw_token_stored is False


def test_github_app_token_exchange_rejects_invalid_ttl_before_planning() -> None:
    with pytest.raises(ValueError, match="^ttl_seconds_invalid$"):
        _request(ttl_seconds=3601)

    with pytest.raises(ValueError, match="^ttl_seconds_invalid$"):
        _request(ttl_seconds=0)

    assert PRIVATE_KEY_FINGERPRINT.startswith("sha256:")
    assert len(PRIVATE_KEY_FINGERPRINT) == 71


def _request(
    *,
    mode: str = "plan_only",
    ttl_seconds: int = 3600,
) -> GitHubAppTokenExchangeRequest:
    return GitHubAppTokenExchangeRequest(
        request_id="github-app-token-exchange-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        repository_owner="tamirat-wubie",
        repository_name="mullu-control-plane",
        app_id=12345,
        installation_id=67890,
        private_key_fingerprint=PRIVATE_KEY_FINGERPRINT,
        ttl_seconds=ttl_seconds,
        requested_permissions={"checks": "write", "contents": "read"},
        mode=mode,
        evidence_refs=["proof://github-app/token-exchange/readiness-1"],
    )
