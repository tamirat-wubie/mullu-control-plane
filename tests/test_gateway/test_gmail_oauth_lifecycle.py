"""Gmail OAuth lifecycle contract tests.

Purpose: prove durable Gmail OAuth refresh planning and response
classification remain secret-redacted, scope-bound, and recovery-aware.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.gmail_oauth_lifecycle.
Invariants:
  - Refresh request plans carry secret references, never secret values.
  - Refresh success records only an access-token digest.
  - Revoked, retryable, and malformed provider outcomes are explicit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.gmail_oauth_lifecycle import (  # noqa: E402
    GMAIL_COMPOSE_SCOPE,
    GMAIL_FULL_MAIL_SCOPE,
    GMAIL_METADATA_SCOPE,
    GMAIL_OAUTH_TOKEN_ENDPOINT,
    GMAIL_READONLY_SCOPE,
    GmailOAuthLifecycleConfig,
    GmailOAuthSecretRefs,
    GmailOAuthWitnessRefs,
    assert_no_secret_values,
    build_refresh_request_plan,
    classify_refresh_response,
    redacted_json,
)


def test_refresh_request_plan_uses_secret_refs_without_values() -> None:
    config = _config()

    plan = build_refresh_request_plan(config)
    payload = plan.as_redacted_dict()
    serialized = redacted_json(payload)

    assert plan.method == "POST"
    assert plan.token_endpoint == GMAIL_OAUTH_TOKEN_ENDPOINT
    assert plan.grant_type == "refresh_token"
    assert payload["secret_ref_by_form_field"]["client_id"] == "secret-ref:gmail-client-id"
    assert payload["secret_ref_by_form_field"]["client_secret"] == "secret-ref:gmail-client-secret"
    assert payload["secret_ref_by_form_field"]["refresh_token"] == "secret-ref:gmail-refresh-token"
    assert payload["scope_ids"] == [GMAIL_READONLY_SCOPE]
    assert payload["secret_values_disclosed"] is False
    assert "client_secret=" not in serialized
    assert "refresh_token=" not in serialized


def test_successful_refresh_response_redacts_access_token_and_sets_schedule() -> None:
    config = _config()

    outcome = classify_refresh_response(
        status_code=200,
        response_payload={
            "access_token": "ya29.runtime-token-value",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": GMAIL_READONLY_SCOPE,
        },
        config=config,
    )
    serialized = json.dumps(outcome.as_redacted_dict(), sort_keys=True)

    assert outcome.status == "refreshed"
    assert outcome.succeeded is True
    assert outcome.retryable is False
    assert outcome.requires_reauthorization is False
    assert len(outcome.access_token_digest) == 64
    assert outcome.next_refresh_after_seconds == 3300
    assert outcome.recovery_action == "store_access_token_by_secret_policy"
    assert outcome.secret_values_disclosed is False
    assert "ya29.runtime-token-value" not in serialized


def test_invalid_grant_requires_reauthorization_and_revocation_evidence() -> None:
    config = _config()

    outcome = classify_refresh_response(
        status_code=400,
        response_payload={"error": "invalid_grant", "error_description": "Token expired"},
        config=config,
    )

    assert outcome.status == "refresh_token_revoked_or_expired"
    assert outcome.succeeded is False
    assert outcome.retryable is False
    assert outcome.requires_reauthorization is True
    assert outcome.error_code == "invalid_grant"
    assert outcome.recovery_action == "halt_for_reauthorization"
    assert "witness:gmail-revocation-recovery" in outcome.evidence_refs
    assert outcome.access_token_digest == ""


def test_retryable_provider_error_stays_retryable_without_reauthorization() -> None:
    config = _config()

    outcome = classify_refresh_response(
        status_code=503,
        response_payload={"error": "backend_error"},
        config=config,
    )

    assert outcome.status == "provider_retryable_error"
    assert outcome.succeeded is False
    assert outcome.retryable is True
    assert outcome.requires_reauthorization is False
    assert outcome.error_code == "backend_error"
    assert outcome.recovery_action == "retry_with_backoff"
    assert outcome.secret_values_disclosed is False


def test_invalid_client_and_scope_errors_are_distinct_recovery_paths() -> None:
    config = _config()

    client_outcome = classify_refresh_response(
        status_code=401,
        response_payload={"error": "invalid_client"},
        config=config,
    )
    scope_outcome = classify_refresh_response(
        status_code=400,
        response_payload={"error": "invalid_scope"},
        config=config,
    )

    assert client_outcome.status == "oauth_client_rejected"
    assert client_outcome.requires_reauthorization is True
    assert client_outcome.recovery_action == "rotate_oauth_client_or_secret"
    assert client_outcome.evidence_refs == ("witness:gmail-oauth-client",)
    assert scope_outcome.status == "scope_rejected"
    assert scope_outcome.requires_reauthorization is True
    assert scope_outcome.recovery_action == "reconcile_least_privilege_scope"
    assert scope_outcome.evidence_refs == ("receipt:gmail-least-privilege-scope",)


def test_malformed_success_payload_fails_closed_without_secret_leakage() -> None:
    config = _config()

    outcome = classify_refresh_response(
        status_code=200,
        response_payload={"access_token": "ya29.runtime-token-value", "token_type": "Mac", "expires_in": 3600},
        config=config,
    )
    serialized = json.dumps(outcome.as_redacted_dict(), sort_keys=True)

    assert outcome.status == "provider_response_invalid"
    assert outcome.succeeded is False
    assert outcome.retryable is False
    assert outcome.requires_reauthorization is False
    assert outcome.error_code == "unsupported_token_type"
    assert outcome.recovery_action == "discard_response_and_investigate_provider_contract"
    assert "ya29.runtime-token-value" not in serialized


def test_short_lived_success_payload_requires_retry_before_admission() -> None:
    config = _config()

    outcome = classify_refresh_response(
        status_code=200,
        response_payload={"access_token": "short-lived-token", "token_type": "Bearer", "expires_in": 301},
        config=config,
    )

    assert outcome.status == "access_token_lifetime_too_short"
    assert outcome.succeeded is False
    assert outcome.retryable is True
    assert outcome.requires_reauthorization is False
    assert outcome.error_code == "expires_in_below_minimum"
    assert outcome.next_refresh_after_seconds == 0
    assert outcome.access_token_digest == ""


def test_config_rejects_overbroad_or_incompatible_scopes() -> None:
    errors: list[str] = []
    for scope_id in (GMAIL_FULL_MAIL_SCOPE, GMAIL_METADATA_SCOPE, GMAIL_COMPOSE_SCOPE):
        try:
            _config(scope_ids=(scope_id,))
        except ValueError as exc:
            errors.append(str(exc))

    assert len(errors) == 3
    assert any("not admitted" in error for error in errors)
    assert any("exactly match" in error for error in errors)
    assert "ya29." not in " ".join(errors)


def test_secret_reference_rejects_secret_material() -> None:
    try:
        GmailOAuthSecretRefs(
            client_id_ref="secret-ref:gmail-client-id",
            client_secret_ref="client_secret=raw-value",
            refresh_token_ref="secret-ref:gmail-refresh-token",
        )
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""

    assert error == "client_secret_ref must not contain secret material"
    assert "raw-value" not in error
    assert "refresh_token=" not in error


def test_assert_no_secret_values_blocks_serialized_secret_markers() -> None:
    try:
        assert_no_secret_values('{"access_token":"ya29.runtime-token-value"}')
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""

    assert error == "serialized Gmail OAuth lifecycle payload contains a prohibited secret marker"
    assert "ya29.runtime-token-value" not in error
    assert "PRIVATE KEY" not in error


def _config(
    *,
    operation_family: str = "read_only_search",
    scope_ids: tuple[str, ...] = (GMAIL_READONLY_SCOPE,),
) -> GmailOAuthLifecycleConfig:
    return GmailOAuthLifecycleConfig(
        connector_id="gmail",
        operation_family=operation_family,
        scope_ids=scope_ids,
        secret_refs=GmailOAuthSecretRefs(
            client_id_ref="secret-ref:gmail-client-id",
            client_secret_ref="secret-ref:gmail-client-secret",
            refresh_token_ref="secret-ref:gmail-refresh-token",
        ),
        witness_refs=GmailOAuthWitnessRefs(
            consent_screen_ref="witness:gmail-consent-screen",
            oauth_client_ref="witness:gmail-oauth-client",
            least_privilege_scope_ref="receipt:gmail-least-privilege-scope",
            refresh_token_storage_ref="receipt:gmail-refresh-token-storage",
            revocation_recovery_ref="witness:gmail-revocation-recovery",
        ),
    )
