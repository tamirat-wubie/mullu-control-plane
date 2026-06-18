"""GitHub App installation-token exchange receipt planner.

Purpose: build hash-bound GitHub App installation-token exchange plans and
    receipts without minting a JWT, loading a private key, calling GitHub, or
    storing a raw installation token.
Governance scope: repository identity, app and installation identity,
    private-key fingerprint, requested permissions, TTL, approval evidence,
    external exchange receipt evidence, response evidence, and secret absence.
Dependencies: dataclasses, re, and command-spine canonical hashing.
Invariants:
  - The planner never calls GitHub, creates JWTs, or loads private keys.
  - Plan-only and dry-run modes cannot claim token exchange response evidence.
  - Exchange-approved mode must bind approval, external execution receipt,
    2xx status, token fingerprint, expiry, and response payload hash evidence.
  - Raw token, JWT, or private-key shaped material blocks receipt admission.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from gateway.command_spine import canonical_hash


GITHUB_APP_TOKEN_EXCHANGE_RECEIPT_SCHEMA_REF = (
    "urn:mullusi:schema:github-app-installation-token-exchange-receipt:1"
)
TOKEN_EXCHANGE_MODES = ("plan_only", "dry_run", "exchange_approved")
TOKEN_EXCHANGE_STATUSES = (
    "planned",
    "dry_run_accepted",
    "exchange_receipt_bound",
    "blocked",
)
REPOSITORY_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
SHA256_REF_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
TOKEN_EXPIRES_AT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
PERMISSION_LEVELS = ("read", "write")
BASE_TOKEN_EXCHANGE_CONTROLS = (
    "github_app_installation_token_endpoint",
    "token_request_payload_hash",
    "app_installation_identity",
    "private_key_fingerprint",
    "bounded_token_ttl",
    "requested_permissions",
    "readiness_evidence",
    "secret_absence",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class GitHubAppTokenExchangeRequest:
    """One governed request to plan or bind a GitHub App token exchange."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    repository_owner: str
    repository_name: str
    app_id: int
    installation_id: int
    private_key_fingerprint: str
    ttl_seconds: int
    requested_permissions: dict[str, str]
    mode: str
    evidence_refs: list[str]
    approval_ref: str = ""
    execution_receipt_ref: str = ""
    response_status_code: int = 0
    token_fingerprint: str = ""
    token_expires_at: str = ""
    response_payload_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "tenant_id",
            "actor_id",
            "command_id",
            "repository_owner",
            "repository_name",
            "private_key_fingerprint",
            "mode",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if not REPOSITORY_SEGMENT_PATTERN.fullmatch(self.repository_owner):
            raise ValueError("repository_owner_invalid")
        if not REPOSITORY_SEGMENT_PATTERN.fullmatch(self.repository_name):
            raise ValueError("repository_name_invalid")
        if not isinstance(self.app_id, int) or self.app_id <= 0:
            raise ValueError("app_id_invalid")
        if not isinstance(self.installation_id, int) or self.installation_id <= 0:
            raise ValueError("installation_id_invalid")
        if not SHA256_REF_PATTERN.fullmatch(self.private_key_fingerprint):
            raise ValueError("private_key_fingerprint_invalid")
        if not isinstance(self.ttl_seconds, int) or not 1 <= self.ttl_seconds <= 3600:
            raise ValueError("ttl_seconds_invalid")
        if self.mode not in TOKEN_EXCHANGE_MODES:
            raise ValueError("github_app_token_exchange_mode_invalid")
        object.__setattr__(self, "requested_permissions", _normalize_permissions(self.requested_permissions))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        for field_name in (
            "approval_ref",
            "execution_receipt_ref",
            "token_fingerprint",
            "token_expires_at",
            "response_payload_hash",
        ):
            object.__setattr__(self, field_name, str(getattr(self, field_name)).strip())
        if not isinstance(self.response_status_code, int) or not 0 <= self.response_status_code <= 599:
            raise ValueError("response_status_code_invalid")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class GitHubAppTokenExchangeReceipt:
    """Schema-backed non-terminal receipt for GitHub App token exchange."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    mode: str
    status: str
    repository_owner: str
    repository_name: str
    app_id: int
    installation_id: int
    endpoint: str
    method: str
    request_payload: dict[str, Any]
    request_payload_hash: str
    private_key_fingerprint: str
    ttl_seconds: int
    requested_permissions: dict[str, str]
    approval_ref: str
    execution_receipt_ref: str
    response_status_code: int
    token_fingerprint: str
    token_expires_at: str
    response_payload_hash: str
    blocked_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    receipt_schema_ref: str
    terminal_closure_required: bool
    external_token_exchange_admitted: bool
    network_call_performed: bool
    private_key_loaded: bool
    jwt_created: bool
    raw_token_stored: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in TOKEN_EXCHANGE_MODES:
            raise ValueError("github_app_token_exchange_mode_invalid")
        if self.status not in TOKEN_EXCHANGE_STATUSES:
            raise ValueError("github_app_token_exchange_status_invalid")
        object.__setattr__(self, "request_payload", dict(self.request_payload))
        object.__setattr__(self, "requested_permissions", _normalize_permissions(self.requested_permissions))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class GitHubAppTokenExchange:
    """Deterministic GitHub App installation-token exchange planner."""

    def evaluate(self, request: GitHubAppTokenExchangeRequest) -> GitHubAppTokenExchangeReceipt:
        """Return a token-exchange receipt without performing token exchange."""
        endpoint = f"/app/installations/{request.installation_id}/access_tokens"
        request_payload = _request_payload(request)
        request_payload_hash = canonical_hash(request_payload)
        blocked_reasons = _blocked_reasons(request)
        required_controls = [*BASE_TOKEN_EXCHANGE_CONTROLS]
        if request.mode == "exchange_approved":
            required_controls.extend(
                [
                    "operator_approval",
                    "github_app_external_exchange_receipt",
                    "github_app_exchange_response_status",
                    "installation_token_fingerprint",
                    "installation_token_expiry",
                    "github_app_exchange_response_hash",
                ]
            )
        if blocked_reasons:
            required_controls.append("github_app_token_exchange_block")

        status = _status(request.mode, blocked_reasons)
        external_exchange_admitted = status == "exchange_receipt_bound"
        receipt = GitHubAppTokenExchangeReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            mode=request.mode,
            status=status,
            repository_owner=request.repository_owner,
            repository_name=request.repository_name,
            app_id=request.app_id,
            installation_id=request.installation_id,
            endpoint=endpoint,
            method="POST",
            request_payload=request_payload,
            request_payload_hash=request_payload_hash,
            private_key_fingerprint=request.private_key_fingerprint,
            ttl_seconds=request.ttl_seconds,
            requested_permissions=request.requested_permissions,
            approval_ref=request.approval_ref,
            execution_receipt_ref=request.execution_receipt_ref,
            response_status_code=request.response_status_code,
            token_fingerprint=request.token_fingerprint,
            token_expires_at=request.token_expires_at,
            response_payload_hash=request.response_payload_hash,
            blocked_reasons=_unique(blocked_reasons),
            required_controls=_unique(required_controls),
            evidence_refs=request.evidence_refs,
            receipt_schema_ref=GITHUB_APP_TOKEN_EXCHANGE_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            external_token_exchange_admitted=external_exchange_admitted,
            network_call_performed=False,
            private_key_loaded=False,
            jwt_created=False,
            raw_token_stored=False,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "github_api_not_called": True,
                "private_key_not_loaded": True,
                "jwt_not_created": True,
                "raw_token_not_stored": True,
                "external_token_exchange_admitted": external_exchange_admitted,
                "payload_hash_bound": bool(request_payload_hash),
                "secret_absence_verified": "secret_values_disclosed" not in blocked_reasons,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"github-app-token-exchange-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _request_payload(request: GitHubAppTokenExchangeRequest) -> dict[str, Any]:
    return {
        "repository_selection": "selected",
        "repositories": [request.repository_name],
        "permissions": dict(request.requested_permissions),
        "ttl_seconds": request.ttl_seconds,
    }


def _blocked_reasons(request: GitHubAppTokenExchangeRequest) -> list[str]:
    blocked: list[str] = []
    if not request.evidence_refs:
        blocked.append("readiness_evidence_refs_required")
    if not request.requested_permissions:
        blocked.append("requested_permissions_required")
    if request.mode in {"plan_only", "dry_run"}:
        blocked.extend(_forbidden_response_evidence(request))
    if request.mode == "exchange_approved":
        blocked.extend(_exchange_approval_violations(request))
    if _contains_secret_material(request.metadata) or _contains_secret_material(_request_payload(request)):
        blocked.append("secret_values_disclosed")
    if _contains_secret_material(request.token_fingerprint) or _contains_secret_material(request.response_payload_hash):
        blocked.append("secret_values_disclosed")
    return blocked


def _forbidden_response_evidence(request: GitHubAppTokenExchangeRequest) -> list[str]:
    blocked: list[str] = []
    if request.approval_ref:
        blocked.append("non_exchange_approval_ref_forbidden")
    if request.execution_receipt_ref:
        blocked.append("non_exchange_execution_receipt_forbidden")
    if request.response_status_code:
        blocked.append("non_exchange_response_status_forbidden")
    if request.token_fingerprint:
        blocked.append("non_exchange_token_fingerprint_forbidden")
    if request.token_expires_at:
        blocked.append("non_exchange_token_expiry_forbidden")
    if request.response_payload_hash:
        blocked.append("non_exchange_response_payload_hash_forbidden")
    return blocked


def _exchange_approval_violations(request: GitHubAppTokenExchangeRequest) -> list[str]:
    blocked: list[str] = []
    if not request.approval_ref:
        blocked.append("approval_ref_required")
    if not request.execution_receipt_ref:
        blocked.append("execution_receipt_ref_required")
    if not 200 <= request.response_status_code <= 299:
        blocked.append("response_status_code_2xx_required")
    if not request.token_fingerprint:
        blocked.append("token_fingerprint_required")
    elif not SHA256_REF_PATTERN.fullmatch(request.token_fingerprint):
        blocked.append("token_fingerprint_invalid")
    if not request.token_expires_at:
        blocked.append("token_expires_at_required")
    elif not TOKEN_EXPIRES_AT_PATTERN.fullmatch(request.token_expires_at):
        blocked.append("token_expires_at_invalid")
    if not request.response_payload_hash:
        blocked.append("response_payload_hash_required")
    elif not SHA256_REF_PATTERN.fullmatch(request.response_payload_hash):
        blocked.append("response_payload_hash_invalid")
    return blocked


def _status(mode: str, blocked_reasons: list[str]) -> str:
    if blocked_reasons:
        return "blocked"
    if mode == "plan_only":
        return "planned"
    if mode == "dry_run":
        return "dry_run_accepted"
    return "exchange_receipt_bound"


def _contains_secret_material(value: Any) -> bool:
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SECRET_PATTERNS)
    if isinstance(value, dict):
        return any(_contains_secret_material(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_secret_material(item) for item in value)
    return False


def _normalize_permissions(values: dict[str, str]) -> dict[str, str]:
    permissions: dict[str, str] = {}
    for key, value in values.items():
        permission = str(key).strip()
        level = str(value).strip()
        if not permission:
            raise ValueError("permission_name_required")
        if level not in PERMISSION_LEVELS:
            raise ValueError("permission_level_invalid")
        permissions[permission] = level
    return permissions


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
