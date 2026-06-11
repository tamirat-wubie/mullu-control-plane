"""Gmail OAuth lifecycle contract for durable connector runtime.

Purpose: model Gmail OAuth refresh, rotation, revocation, and failed-refresh
    recovery without performing provider calls or serializing credential values.
Governance scope: OAuth scope minimization, secret-reference handling,
    token-response redaction, revocation recovery, retry classification, and
    receipt-compatible evidence.
Dependencies: stdlib dataclasses, hashlib, json, and Gmail OAuth token endpoint
    contracts.
Invariants:
  - Secret values are accepted only inside transient provider response payloads.
  - Access-token, refresh-token, client-secret, and private-key values are never
    returned by public objects.
  - Scope selection must match the declared Gmail operation family exactly.
  - Revoked or expired refresh tokens require reauthorization evidence before
    another durable runtime claim.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any


GMAIL_OAUTH_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_METADATA_SCOPE = "https://www.googleapis.com/auth/gmail.metadata"
GMAIL_FULL_MAIL_SCOPE = "https://mail.google.com/"

MINIMUM_SCOPE_BY_OPERATION_FAMILY = {
    "read_only_search": frozenset({GMAIL_READONLY_SCOPE}),
    "read_only_message": frozenset({GMAIL_READONLY_SCOPE}),
    "draft_create": frozenset({GMAIL_COMPOSE_SCOPE}),
    "send_with_approval": frozenset({GMAIL_SEND_SCOPE}),
    "read_and_draft": frozenset({GMAIL_READONLY_SCOPE, GMAIL_COMPOSE_SCOPE}),
    "read_and_send_with_approval": frozenset({GMAIL_READONLY_SCOPE, GMAIL_SEND_SCOPE}),
}

SECRET_MARKERS = (
    "ya29.",
    "refresh_token=",
    "client_secret=",
    "-----BEGIN PRIVATE KEY-----",
)


@dataclass(frozen=True, slots=True)
class GmailOAuthSecretRefs:
    """Presence-only references for Gmail OAuth secret material."""

    client_id_ref: str
    client_secret_ref: str
    refresh_token_ref: str

    def __post_init__(self) -> None:
        _require_reference(self.client_id_ref, "client_id_ref")
        _require_reference(self.client_secret_ref, "client_secret_ref")
        _require_reference(self.refresh_token_ref, "refresh_token_ref")


@dataclass(frozen=True, slots=True)
class GmailOAuthWitnessRefs:
    """Witness references required before durable Gmail OAuth can run."""

    consent_screen_ref: str
    oauth_client_ref: str
    least_privilege_scope_ref: str
    refresh_token_storage_ref: str
    revocation_recovery_ref: str

    def __post_init__(self) -> None:
        _require_reference(self.consent_screen_ref, "consent_screen_ref")
        _require_reference(self.oauth_client_ref, "oauth_client_ref")
        _require_reference(self.least_privilege_scope_ref, "least_privilege_scope_ref")
        _require_reference(self.refresh_token_storage_ref, "refresh_token_storage_ref")
        _require_reference(self.revocation_recovery_ref, "revocation_recovery_ref")


@dataclass(frozen=True, slots=True)
class GmailOAuthLifecycleConfig:
    """Static contract for one durable Gmail OAuth runtime boundary."""

    connector_id: str
    operation_family: str
    scope_ids: tuple[str, ...]
    secret_refs: GmailOAuthSecretRefs
    witness_refs: GmailOAuthWitnessRefs
    token_endpoint: str = GMAIL_OAUTH_TOKEN_ENDPOINT
    refresh_margin_seconds: int = 300
    minimum_expires_in_seconds: int = 600

    def __post_init__(self) -> None:
        if self.connector_id != "gmail":
            raise ValueError("Gmail OAuth lifecycle config only supports connector_id=gmail")
        if self.token_endpoint != GMAIL_OAUTH_TOKEN_ENDPOINT:
            raise ValueError("Gmail OAuth token_endpoint must use the governed Google token endpoint")
        if self.refresh_margin_seconds < 0:
            raise ValueError("refresh_margin_seconds must be non-negative")
        if self.minimum_expires_in_seconds <= self.refresh_margin_seconds:
            raise ValueError("minimum_expires_in_seconds must exceed refresh_margin_seconds")
        normalized_scopes = tuple(_require_scope(scope) for scope in self.scope_ids)
        object.__setattr__(self, "scope_ids", normalized_scopes)
        expected_scopes = MINIMUM_SCOPE_BY_OPERATION_FAMILY.get(self.operation_family)
        if expected_scopes is None:
            raise ValueError("Gmail OAuth operation_family is unsupported")
        if frozenset(normalized_scopes) != expected_scopes:
            raise ValueError("Gmail OAuth scope_ids must exactly match the operation family minimum")


@dataclass(frozen=True, slots=True)
class GmailOAuthRefreshRequestPlan:
    """Secret-reference-only plan for a Gmail OAuth refresh request."""

    method: str
    token_endpoint: str
    content_type: str
    grant_type: str
    secret_ref_by_form_field: dict[str, str]
    scope_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    secret_values_disclosed: bool = False

    def as_redacted_dict(self) -> dict[str, Any]:
        """Return a JSON-safe request plan without secret values."""

        return {
            "method": self.method,
            "token_endpoint": self.token_endpoint,
            "content_type": self.content_type,
            "grant_type": self.grant_type,
            "secret_ref_by_form_field": dict(self.secret_ref_by_form_field),
            "scope_ids": list(self.scope_ids),
            "evidence_refs": list(self.evidence_refs),
            "secret_values_disclosed": self.secret_values_disclosed,
        }


@dataclass(frozen=True, slots=True)
class GmailOAuthRefreshOutcome:
    """Receipt-compatible classification of one token-refresh response."""

    status: str
    succeeded: bool
    retryable: bool
    requires_reauthorization: bool
    access_token_digest: str
    token_type: str
    expires_in_seconds: int
    next_refresh_after_seconds: int
    error_code: str
    recovery_action: str
    evidence_refs: tuple[str, ...]
    secret_values_disclosed: bool = False

    def as_redacted_dict(self) -> dict[str, Any]:
        """Return a JSON-safe refresh outcome without token values."""

        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        return payload


def build_refresh_request_plan(config: GmailOAuthLifecycleConfig) -> GmailOAuthRefreshRequestPlan:
    """Build a secret-reference-only Gmail OAuth refresh request plan."""

    return GmailOAuthRefreshRequestPlan(
        method="POST",
        token_endpoint=config.token_endpoint,
        content_type="application/x-www-form-urlencoded",
        grant_type="refresh_token",
        secret_ref_by_form_field={
            "client_id": config.secret_refs.client_id_ref,
            "client_secret": config.secret_refs.client_secret_ref,
            "refresh_token": config.secret_refs.refresh_token_ref,
        },
        scope_ids=config.scope_ids,
        evidence_refs=(
            config.witness_refs.oauth_client_ref,
            config.witness_refs.refresh_token_storage_ref,
            config.witness_refs.least_privilege_scope_ref,
        ),
    )


def classify_refresh_response(
    *,
    status_code: int,
    response_payload: Mapping[str, Any],
    config: GmailOAuthLifecycleConfig,
) -> GmailOAuthRefreshOutcome:
    """Classify a Gmail OAuth refresh response without returning secret values."""

    if status_code == 200:
        return _classify_success_payload(response_payload, config)
    error_code = _safe_error_code(response_payload.get("error"))
    if status_code in {408, 429} or status_code >= 500:
        return _failed_outcome(
            status="provider_retryable_error",
            retryable=True,
            requires_reauthorization=False,
            error_code=error_code or f"http_{status_code}",
            recovery_action="retry_with_backoff",
            evidence_refs=(config.witness_refs.refresh_token_storage_ref,),
        )
    if error_code == "invalid_grant":
        return _failed_outcome(
            status="refresh_token_revoked_or_expired",
            retryable=False,
            requires_reauthorization=True,
            error_code=error_code,
            recovery_action="halt_for_reauthorization",
            evidence_refs=(
                config.witness_refs.refresh_token_storage_ref,
                config.witness_refs.revocation_recovery_ref,
            ),
        )
    if error_code == "invalid_client":
        return _failed_outcome(
            status="oauth_client_rejected",
            retryable=False,
            requires_reauthorization=True,
            error_code=error_code,
            recovery_action="rotate_oauth_client_or_secret",
            evidence_refs=(config.witness_refs.oauth_client_ref,),
        )
    if error_code == "invalid_scope":
        return _failed_outcome(
            status="scope_rejected",
            retryable=False,
            requires_reauthorization=True,
            error_code=error_code,
            recovery_action="reconcile_least_privilege_scope",
            evidence_refs=(config.witness_refs.least_privilege_scope_ref,),
        )
    return _failed_outcome(
        status="provider_denied_refresh",
        retryable=False,
        requires_reauthorization=True,
        error_code=error_code or f"http_{status_code}",
        recovery_action="halt_for_operator_review",
        evidence_refs=(config.witness_refs.revocation_recovery_ref,),
    )


def assert_no_secret_values(serialized_payload: str) -> None:
    """Raise if a serialized lifecycle payload contains prohibited secret markers."""

    for marker in SECRET_MARKERS:
        if marker in serialized_payload:
            raise ValueError("serialized Gmail OAuth lifecycle payload contains a prohibited secret marker")


def _classify_success_payload(
    response_payload: Mapping[str, Any],
    config: GmailOAuthLifecycleConfig,
) -> GmailOAuthRefreshOutcome:
    access_token = response_payload.get("access_token")
    token_type = response_payload.get("token_type")
    expires_in = response_payload.get("expires_in")
    if not isinstance(access_token, str) or not access_token.strip():
        return _failed_outcome(
            status="provider_response_invalid",
            retryable=False,
            requires_reauthorization=False,
            error_code="missing_access_token",
            recovery_action="discard_response_and_investigate_provider_contract",
            evidence_refs=(config.witness_refs.refresh_token_storage_ref,),
        )
    if token_type != "Bearer":
        return _failed_outcome(
            status="provider_response_invalid",
            retryable=False,
            requires_reauthorization=False,
            error_code="unsupported_token_type",
            recovery_action="discard_response_and_investigate_provider_contract",
            evidence_refs=(config.witness_refs.refresh_token_storage_ref,),
        )
    if not isinstance(expires_in, int) or expires_in <= 0:
        return _failed_outcome(
            status="provider_response_invalid",
            retryable=False,
            requires_reauthorization=False,
            error_code="invalid_expires_in",
            recovery_action="discard_response_and_investigate_provider_contract",
            evidence_refs=(config.witness_refs.refresh_token_storage_ref,),
        )
    if expires_in < config.minimum_expires_in_seconds:
        return _failed_outcome(
            status="access_token_lifetime_too_short",
            retryable=True,
            requires_reauthorization=False,
            error_code="expires_in_below_minimum",
            recovery_action="retry_or_reauthorize_before_runtime_admission",
            evidence_refs=(config.witness_refs.refresh_token_storage_ref,),
        )
    access_token_digest = hashlib.sha256(access_token.encode("utf-8")).hexdigest()
    next_refresh_after_seconds = max(0, expires_in - config.refresh_margin_seconds)
    return GmailOAuthRefreshOutcome(
        status="refreshed",
        succeeded=True,
        retryable=False,
        requires_reauthorization=False,
        access_token_digest=access_token_digest,
        token_type=token_type,
        expires_in_seconds=expires_in,
        next_refresh_after_seconds=next_refresh_after_seconds,
        error_code="",
        recovery_action="store_access_token_by_secret_policy",
        evidence_refs=(
            config.witness_refs.refresh_token_storage_ref,
            f"gmail_oauth_refresh:{access_token_digest[:16]}",
        ),
    )


def _failed_outcome(
    *,
    status: str,
    retryable: bool,
    requires_reauthorization: bool,
    error_code: str,
    recovery_action: str,
    evidence_refs: tuple[str, ...],
) -> GmailOAuthRefreshOutcome:
    return GmailOAuthRefreshOutcome(
        status=status,
        succeeded=False,
        retryable=retryable,
        requires_reauthorization=requires_reauthorization,
        access_token_digest="",
        token_type="",
        expires_in_seconds=0,
        next_refresh_after_seconds=0,
        error_code=error_code,
        recovery_action=recovery_action,
        evidence_refs=evidence_refs,
    )


def _require_reference(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty reference")
    if _contains_secret_marker(value):
        raise ValueError(f"{field_name} must not contain secret material")
    return value.strip()


def _require_scope(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("scope_ids must contain non-empty scope strings")
    normalized = value.strip()
    if normalized in {GMAIL_METADATA_SCOPE, GMAIL_FULL_MAIL_SCOPE}:
        raise ValueError("scope_ids include a scope not admitted by the durable Gmail lifecycle")
    return normalized


def _safe_error_code(value: object) -> str:
    if not isinstance(value, str):
        return ""
    if _contains_secret_marker(value):
        return "redacted_provider_error"
    stripped = value.strip()
    if not stripped:
        return ""
    return "".join(ch for ch in stripped if ch.isalnum() or ch in {"_", "-"})[:80]


def _contains_secret_marker(value: str) -> bool:
    return any(marker in value for marker in SECRET_MARKERS)


def redacted_json(payload: Mapping[str, Any]) -> str:
    """Serialize a lifecycle payload and enforce secret-marker exclusion."""

    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert_no_secret_values(serialized)
    return serialized
