"""Gateway temporal credential expiry evaluator.

Purpose: prove a credential descriptor is active, scoped, unexpired, and
    rotation-aware before governed connector dispatch.
Governance scope: runtime-owned credential expiry, provider and scope binding,
    rotation windows, credential lifecycle state, evidence refs, high-risk
    source receipt binding, no-secret serialization, and non-terminal receipts.
Dependencies: dataclasses, datetime, command-spine canonical hashing, and the
    Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns credential expiry truth.
  - Credential values are never accepted or serialized by this receipt.
  - Expired, revoked, future-dated, wrong-provider, or wrong-scope credentials fail closed.
  - Rotation-pending credentials warn before dispatch and block after rotation due.
  - High-risk connector dispatch binds temporal, reapproval, and binding receipts.
  - Temporal credential expiry receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_CREDENTIAL_EXPIRY_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-credential-expiry-receipt:1"
RISK_LEVELS = ("low", "medium", "high", "critical")
CREDENTIAL_SOURCE_KINDS = ("environment", "file", "vault", "operator_input")
CREDENTIAL_DISPOSITIONS = ("active", "rotation_pending", "expired", "revoked")
CREDENTIAL_STATUSES = ("credential_valid", "rotation_pending", "expired", "blocked", "not_required")
CREDENTIAL_STATES = (
    "active",
    "rotation_pending",
    "expired",
    "revoked",
    "future",
    "wrong_scope",
    "invalid",
    "not_required",
)
HIGH_RISK_LEVELS = frozenset({"high", "critical"})
SECRET_METADATA_KEYS = frozenset(
    {
        "api_key",
        "credential_value",
        "password",
        "raw_secret",
        "raw_value",
        "secret",
        "secret_value",
        "token",
    }
)
BASE_CREDENTIAL_EXPIRY_CONTROLS = (
    "runtime_clock",
    "credential_expiry",
    "credential_scope",
    "credential_lifecycle",
    "rotation_window",
    "evidence_reference",
    "secret_value_absence",
    "temporal_credential_expiry_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class CredentialDescriptor:
    """Secret-free credential descriptor proposed for connector dispatch."""

    credential_id: str
    tenant_id: str
    provider_id: str
    credential_scope_id: str
    source_kind: str
    disposition: str
    issued_at: str
    observed_at: str
    expires_at: str
    owner_id: str
    evidence_refs: list[str]
    rotation_due_at: str = ""
    source_binding_receipt_id: str = ""
    replaced_by_credential_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "credential_id",
            "tenant_id",
            "provider_id",
            "credential_scope_id",
            "source_kind",
            "disposition",
            "issued_at",
            "observed_at",
            "expires_at",
            "owner_id",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.source_kind not in CREDENTIAL_SOURCE_KINDS:
            raise ValueError("credential_source_kind_invalid")
        if self.disposition not in CREDENTIAL_DISPOSITIONS:
            raise ValueError("credential_disposition_invalid")
        _raise_if_secret_metadata(self.metadata)
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "rotation_due_at", str(self.rotation_due_at).strip())
        object.__setattr__(self, "source_binding_receipt_id", str(self.source_binding_receipt_id).strip())
        object.__setattr__(self, "replaced_by_credential_id", str(self.replaced_by_credential_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalCredentialPolicy:
    """Tenant policy defining credential expiry and scope checks."""

    policy_id: str
    tenant_id: str
    allowed_provider_ids: list[str]
    allowed_credential_scope_ids: list[str]
    rotation_warning_seconds: int = 0
    max_credential_age_seconds: int = 0
    requires_credential_check: bool = True
    high_risk_requires_credential_check: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.rotation_warning_seconds < 0:
            raise ValueError("rotation_warning_seconds_nonnegative_required")
        if self.max_credential_age_seconds < 0:
            raise ValueError("max_credential_age_seconds_nonnegative_required")
        _raise_if_secret_metadata(self.metadata)
        object.__setattr__(self, "allowed_provider_ids", _normalize_list(self.allowed_provider_ids))
        object.__setattr__(
            self,
            "allowed_credential_scope_ids",
            _normalize_list(self.allowed_credential_scope_ids),
        )
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalCredentialRequest:
    """One request to recheck credential expiry before connector dispatch."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    provider_id: str
    credential_scope_id: str
    policy: TemporalCredentialPolicy
    evidence_refs: list[str]
    credential: CredentialDescriptor | None = None
    source_temporal_receipt_id: str = ""
    source_reapproval_receipt_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "tenant_id",
            "actor_id",
            "command_id",
            "action_type",
            "risk_level",
            "provider_id",
            "credential_scope_id",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.risk_level not in RISK_LEVELS:
            raise ValueError("risk_level_invalid")
        _raise_if_secret_metadata(self.metadata)
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "source_temporal_receipt_id", str(self.source_temporal_receipt_id).strip())
        object.__setattr__(self, "source_reapproval_receipt_id", str(self.source_reapproval_receipt_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalCredentialExpiryReceipt:
    """Schema-backed non-terminal receipt for credential expiry checks."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    status: str
    credential_state: str
    runtime_now_utc: str
    credential_check_required: bool
    credential_id: str
    provider_id: str
    credential_scope_id: str
    source_kind: str
    disposition: str
    issued_at: str
    observed_at: str
    expires_at: str
    rotation_due_at: str
    seconds_until_expiry: int
    seconds_until_rotation_due: int
    credential_age_seconds: int
    owner_id: str
    allowed_provider_ids: list[str]
    allowed_credential_scope_ids: list[str]
    blocked_reasons: list[str]
    warning_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    credential_evidence_refs: list[str]
    source_binding_receipt_id: str
    source_temporal_receipt_id: str
    source_reapproval_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in CREDENTIAL_STATUSES:
            raise ValueError("temporal_credential_status_invalid")
        if self.credential_state not in CREDENTIAL_STATES:
            raise ValueError("temporal_credential_state_invalid")
        if self.seconds_until_expiry < 0 or self.seconds_until_rotation_due < 0 or self.credential_age_seconds < 0:
            raise ValueError("temporal_credential_seconds_nonnegative_required")
        object.__setattr__(self, "allowed_provider_ids", _normalize_list(self.allowed_provider_ids))
        object.__setattr__(
            self,
            "allowed_credential_scope_ids",
            _normalize_list(self.allowed_credential_scope_ids),
        )
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "warning_reasons", _normalize_list(self.warning_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "credential_evidence_refs", _normalize_list(self.credential_evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalCredentialExpiry:
    """Deterministic runtime credential expiry evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: TemporalCredentialRequest) -> TemporalCredentialExpiryReceipt:
        """Return whether a credential descriptor may authorize dispatch now."""
        now = _parse_required_instant(self._clock.now_utc())
        credential_check_required = _credential_check_required(request)
        blocked_reasons: list[str] = []
        warning_reasons: list[str] = []
        required_controls = [*BASE_CREDENTIAL_EXPIRY_CONTROLS]

        if credential_check_required:
            required_controls.append("credential_policy")
        if request.risk_level in HIGH_RISK_LEVELS:
            required_controls.append("high_risk_credential_binding")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")
        if request.source_reapproval_receipt_id:
            required_controls.append("source_reapproval_receipt")

        blocked_reasons.extend(_policy_violations(request, credential_check_required))
        credential = request.credential
        issued_at: datetime | None = None
        observed_at: datetime | None = None
        expires_at: datetime | None = None
        rotation_due_at: datetime | None = None
        if credential is not None:
            issued_at = _parse_optional_instant(credential.issued_at, blocked_reasons, "issued_at_invalid")
            observed_at = _parse_optional_instant(credential.observed_at, blocked_reasons, "observed_at_invalid")
            expires_at = _parse_optional_instant(credential.expires_at, blocked_reasons, "expires_at_invalid")
            rotation_due_at = _parse_optional_instant(
                credential.rotation_due_at,
                blocked_reasons,
                "rotation_due_at_invalid",
            )
            _apply_credential_rules(
                request=request,
                now=now,
                issued_at=issued_at,
                observed_at=observed_at,
                expires_at=expires_at,
                rotation_due_at=rotation_due_at,
                blocked_reasons=blocked_reasons,
                warning_reasons=warning_reasons,
            )

        status = _status(blocked_reasons, warning_reasons, credential_check_required)
        credential_state = _credential_state(credential, blocked_reasons, status)
        receipt = TemporalCredentialExpiryReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            policy_id=request.policy.policy_id,
            status=status,
            credential_state=credential_state,
            runtime_now_utc=now.isoformat(),
            credential_check_required=credential_check_required,
            credential_id=credential.credential_id if credential else "",
            provider_id=credential.provider_id if credential else request.provider_id,
            credential_scope_id=credential.credential_scope_id if credential else request.credential_scope_id,
            source_kind=credential.source_kind if credential else "",
            disposition=credential.disposition if credential else "",
            issued_at=_instant_text(issued_at, credential.issued_at if credential else ""),
            observed_at=_instant_text(observed_at, credential.observed_at if credential else ""),
            expires_at=_instant_text(expires_at, credential.expires_at if credential else ""),
            rotation_due_at=_instant_text(rotation_due_at, credential.rotation_due_at if credential else ""),
            seconds_until_expiry=_seconds_until(now, expires_at),
            seconds_until_rotation_due=_seconds_until(now, rotation_due_at),
            credential_age_seconds=_credential_age_seconds(now, issued_at),
            owner_id=credential.owner_id if credential else "",
            allowed_provider_ids=request.policy.allowed_provider_ids,
            allowed_credential_scope_ids=request.policy.allowed_credential_scope_ids,
            blocked_reasons=_unique(blocked_reasons),
            warning_reasons=_unique(warning_reasons),
            required_controls=_unique(
                required_controls
                if status in {"credential_valid", "rotation_pending", "not_required"}
                else [*required_controls, "credential_dispatch_block"]
            ),
            evidence_refs=request.evidence_refs,
            credential_evidence_refs=credential.evidence_refs if credential else [],
            source_binding_receipt_id=credential.source_binding_receipt_id if credential else "",
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            source_reapproval_receipt_id=request.source_reapproval_receipt_id,
            receipt_schema_ref=TEMPORAL_CREDENTIAL_EXPIRY_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "dispatch_allowed": status in {"credential_valid", "rotation_pending", "not_required"},
                "credential_checked": credential_check_required,
                "expiry_checked": credential_check_required and credential is not None,
                "provider_scope_checked": credential_check_required and credential is not None,
                "rotation_warning_checked": credential_check_required and credential is not None,
                "secret_value_absent": True,
                "high_risk_source_receipts_checked": _source_receipts_checked(request),
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-credential-expiry-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _credential_check_required(request: TemporalCredentialRequest) -> bool:
    if request.policy.requires_credential_check:
        return True
    return request.risk_level in HIGH_RISK_LEVELS and request.policy.high_risk_requires_credential_check


def _policy_violations(request: TemporalCredentialRequest, credential_check_required: bool) -> list[str]:
    violations: list[str] = []
    if request.policy.tenant_id != request.tenant_id:
        violations.append("policy_tenant_mismatch")
    if not credential_check_required:
        return violations
    if not request.policy.allowed_provider_ids:
        violations.append("allowed_provider_ids_required")
    if not request.policy.allowed_credential_scope_ids:
        violations.append("allowed_credential_scope_ids_required")
    if request.credential is None:
        violations.append("credential_required")
    if not request.evidence_refs:
        violations.append("evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_temporal_receipt_id:
        violations.append("source_temporal_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_reapproval_receipt_id:
        violations.append("source_reapproval_receipt_required_for_high_risk")
    return violations


def _apply_credential_rules(
    *,
    request: TemporalCredentialRequest,
    now: datetime,
    issued_at: datetime | None,
    observed_at: datetime | None,
    expires_at: datetime | None,
    rotation_due_at: datetime | None,
    blocked_reasons: list[str],
    warning_reasons: list[str],
) -> None:
    credential = request.credential
    if credential is None:
        return
    if credential.tenant_id != request.tenant_id:
        blocked_reasons.append("credential_tenant_mismatch")
    if credential.provider_id != request.provider_id:
        blocked_reasons.append("credential_provider_mismatch")
    if credential.credential_scope_id != request.credential_scope_id:
        blocked_reasons.append("credential_scope_mismatch")
    if credential.provider_id not in request.policy.allowed_provider_ids:
        blocked_reasons.append("credential_provider_not_allowed")
    if credential.credential_scope_id not in request.policy.allowed_credential_scope_ids:
        blocked_reasons.append("credential_scope_not_allowed")
    if credential.disposition == "expired":
        blocked_reasons.append("credential_expired")
    elif credential.disposition == "revoked":
        blocked_reasons.append("credential_revoked")
    elif credential.disposition == "rotation_pending":
        warning_reasons.append("credential_rotation_pending")
    if issued_at is None:
        blocked_reasons.append("issued_at_required")
    elif issued_at > now:
        blocked_reasons.append("credential_future")
    if observed_at is None:
        blocked_reasons.append("observed_at_required")
    elif observed_at > now:
        blocked_reasons.append("credential_observed_in_future")
    if expires_at is None:
        blocked_reasons.append("expires_at_required")
    elif expires_at <= now:
        blocked_reasons.append("credential_expired")
    if rotation_due_at and rotation_due_at <= now:
        blocked_reasons.append("credential_rotation_overdue")
    if request.policy.max_credential_age_seconds and issued_at:
        age_seconds = _credential_age_seconds(now, issued_at)
        if age_seconds > request.policy.max_credential_age_seconds:
            blocked_reasons.append("credential_too_old")
    if not credential.owner_id:
        blocked_reasons.append("owner_id_required")
    if not credential.evidence_refs:
        blocked_reasons.append("credential_evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS and not credential.source_binding_receipt_id:
        blocked_reasons.append("source_binding_receipt_required_for_high_risk")
    if expires_at and expires_at > now and _within_warning_window(now, expires_at, request.policy.rotation_warning_seconds):
        warning_reasons.append("credential_expiry_near")
    if rotation_due_at and rotation_due_at > now and _within_warning_window(
        now,
        rotation_due_at,
        request.policy.rotation_warning_seconds,
    ):
        warning_reasons.append("credential_rotation_due_soon")


def _status(blocked_reasons: list[str], warning_reasons: list[str], credential_check_required: bool) -> str:
    if not credential_check_required:
        return "not_required"
    if "credential_expired" in blocked_reasons:
        return "expired"
    if blocked_reasons:
        return "blocked"
    if any(reason.startswith("credential_") for reason in warning_reasons):
        return "rotation_pending"
    return "credential_valid"


def _credential_state(
    credential: CredentialDescriptor | None,
    blocked_reasons: list[str],
    status: str,
) -> str:
    if status == "not_required":
        return "not_required"
    if credential is None:
        return "invalid"
    if "credential_expired" in blocked_reasons or credential.disposition == "expired":
        return "expired"
    if credential.disposition == "revoked":
        return "revoked"
    if "credential_future" in blocked_reasons or "credential_observed_in_future" in blocked_reasons:
        return "future"
    if any(
        reason in blocked_reasons
        for reason in (
            "credential_provider_mismatch",
            "credential_scope_mismatch",
            "credential_provider_not_allowed",
            "credential_scope_not_allowed",
        )
    ):
        return "wrong_scope"
    if credential.disposition == "rotation_pending" or status == "rotation_pending":
        return "rotation_pending"
    if blocked_reasons:
        return "invalid"
    return "active"


def _source_receipts_checked(request: TemporalCredentialRequest) -> bool:
    if request.risk_level not in HIGH_RISK_LEVELS:
        return False
    return all(
        (
            request.source_temporal_receipt_id,
            request.source_reapproval_receipt_id,
            request.credential and request.credential.source_binding_receipt_id,
        )
    )


def _within_warning_window(now: datetime, expires_at: datetime, warning_seconds: int) -> bool:
    if warning_seconds <= 0:
        return False
    return 0 <= (expires_at - now).total_seconds() <= warning_seconds


def _seconds_until(now: datetime, target: datetime | None) -> int:
    if target is None:
        return 0
    return max(0, int((target - now).total_seconds()))


def _credential_age_seconds(now: datetime, issued_at: datetime | None) -> int:
    if issued_at is None:
        return 0
    return max(0, int((now - issued_at).total_seconds()))


def _parse_optional_instant(value: str, violations: list[str], reason: str) -> datetime | None:
    if not value:
        return None
    try:
        return _parse_required_instant(value)
    except ValueError:
        violations.append(reason)
        return None


def _parse_required_instant(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("instant_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("instant_timezone_required")
    return parsed.astimezone(timezone.utc)


def _instant_text(value: datetime | None, fallback: str) -> str:
    return value.isoformat() if value else fallback


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _raise_if_secret_metadata(metadata: dict[str, Any]) -> None:
    forbidden = sorted(str(key).lower() for key in metadata if str(key).lower() in SECRET_METADATA_KEYS)
    if forbidden:
        raise ValueError(f"secret_metadata_keys_forbidden:{','.join(forbidden)}")
