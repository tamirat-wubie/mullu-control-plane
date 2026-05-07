"""Gateway connector self-healing receipts.

Purpose: classify connector failures and emit bounded recovery receipts without
claiming success before verification.
Governance scope: provider failure handling, retry bounds, fallback providers,
read-only degradation, incident opening, capability revocation, and evidence-
backed recovery receipts.
Dependencies: dataclasses, enum, and command-spine canonical hashing.
Invariants:
  - Connector failures require evidence refs.
  - Recovery actions must be declared by policy.
  - Write-operation failures require operator review before continuation.
  - Missing receipts can revoke capability use until proof is restored.
  - Healing receipts are not terminal command closure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any

from gateway.command_spine import canonical_hash


class ConnectorFailureType(StrEnum):
    """Classified connector failure type."""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTH_EXPIRED = "auth_expired"
    PROVIDER_ERROR = "provider_error"
    RECEIPT_MISSING = "receipt_missing"
    UNSAFE_RESPONSE = "unsafe_response"


class ConnectorRecoveryAction(StrEnum):
    """Policy-declared recovery action."""

    RETRY = "retry"
    SWITCH_PROVIDER = "switch_provider"
    DEGRADE_READ_ONLY = "degrade_read_only"
    OPEN_INCIDENT = "open_incident"
    REVOKE_CAPABILITY = "revoke_capability"
    REQUIRE_REVIEW = "require_review"


class ConnectorHealingStatus(StrEnum):
    """Resulting self-healing status."""

    RETRY_SCHEDULED = "retry_scheduled"
    PROVIDER_SWITCH_REQUIRED = "provider_switch_required"
    DEGRADED_READ_ONLY = "degraded_read_only"
    INCIDENT_OPENED = "incident_opened"
    CAPABILITY_REVOKED = "capability_revoked"
    REQUIRES_REVIEW = "requires_review"


@dataclass(frozen=True, slots=True)
class ConnectorFailure:
    """Observed provider or connector failure."""

    failure_id: str
    connector_id: str
    provider: str
    operation: str
    tenant_id: str
    failure_type: ConnectorFailureType
    observed_at: str
    retryable: bool
    evidence_refs: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("failure_id", "connector_id", "provider", "operation", "tenant_id", "observed_at"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.failure_type, ConnectorFailureType):
            raise ValueError("connector_failure_type_invalid")
        if not isinstance(self.retryable, bool):
            raise ValueError("retryable_boolean_required")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class ConnectorRecoveryPolicy:
    """Policy envelope for one connector's recovery behavior."""

    connector_id: str
    allowed_actions: tuple[ConnectorRecoveryAction, ...]
    max_retry_attempts: int
    fallback_providers: tuple[str, ...] = ()
    requires_receipt: bool = True
    requires_operator_review_for_write: bool = True
    incident_queue: str = "connector-ops"

    def __post_init__(self) -> None:
        _require_text(self.connector_id, "connector_id")
        actions = tuple(self.allowed_actions)
        if not actions:
            raise ValueError("allowed_actions_required")
        for action in actions:
            if not isinstance(action, ConnectorRecoveryAction):
                raise ValueError("connector_recovery_action_invalid")
        if not isinstance(self.max_retry_attempts, int) or isinstance(self.max_retry_attempts, bool):
            raise ValueError("max_retry_attempts_integer_required")
        if self.max_retry_attempts < 0:
            raise ValueError("max_retry_attempts_nonnegative_required")
        object.__setattr__(self, "allowed_actions", actions)
        object.__setattr__(self, "fallback_providers", _normalize_text_tuple(self.fallback_providers, "fallback_providers", allow_empty=True))
        _require_text(self.incident_queue, "incident_queue")


@dataclass(frozen=True, slots=True)
class ConnectorHealingReceipt:
    """Non-terminal receipt for one connector recovery decision."""

    receipt_id: str
    connector_id: str
    tenant_id: str
    failure_id: str
    action: ConnectorRecoveryAction
    status: ConnectorHealingStatus
    safe_to_continue: bool
    retry_after_seconds: int
    fallback_provider: str
    required_controls: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    receipt_is_terminal_closure: bool = False
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("receipt_id", "connector_id", "tenant_id", "failure_id"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.action, ConnectorRecoveryAction):
            raise ValueError("connector_recovery_action_invalid")
        if not isinstance(self.status, ConnectorHealingStatus):
            raise ValueError("connector_healing_status_invalid")
        if self.receipt_is_terminal_closure:
            raise ValueError("healing_receipt_is_not_terminal_closure")
        if not isinstance(self.retry_after_seconds, int) or isinstance(self.retry_after_seconds, bool):
            raise ValueError("retry_after_seconds_integer_required")
        if self.retry_after_seconds < 0:
            raise ValueError("retry_after_seconds_nonnegative_required")
        object.__setattr__(self, "required_controls", _normalize_text_tuple(self.required_controls, "required_controls", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _receipt_metadata(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


class ConnectorSelfHealingEngine:
    """Evaluate connector failures against bounded recovery policy."""

    def evaluate(
        self,
        failure: ConnectorFailure,
        policy: ConnectorRecoveryPolicy,
        *,
        attempt_count: int = 0,
        write_operation: bool = False,
        receipt_ref: str = "",
    ) -> ConnectorHealingReceipt:
        """Return the governed recovery receipt for one connector failure."""
        if failure.connector_id != policy.connector_id:
            raise ValueError("failure_policy_connector_mismatch")
        if not isinstance(attempt_count, int) or isinstance(attempt_count, bool):
            raise ValueError("attempt_count_integer_required")
        if attempt_count < 0:
            raise ValueError("attempt_count_nonnegative_required")
        evidence_refs = _combined_refs(failure.evidence_refs, (receipt_ref,) if receipt_ref else ())

        if write_operation and policy.requires_operator_review_for_write:
            return _stamp_receipt(_receipt(failure, ConnectorRecoveryAction.REQUIRE_REVIEW, ConnectorHealingStatus.REQUIRES_REVIEW, False, 0, "", ("operator_review", "connector_receipt"), evidence_refs, {"write_operation_blocked": True}))
        if policy.requires_receipt and failure.failure_type == ConnectorFailureType.RECEIPT_MISSING:
            return self._receipt_missing(failure, policy, evidence_refs)
        if failure.failure_type in {ConnectorFailureType.AUTH_EXPIRED, ConnectorFailureType.UNSAFE_RESPONSE}:
            return self._unsafe_or_auth_failure(failure, policy, evidence_refs)
        if failure.retryable and attempt_count < policy.max_retry_attempts and _allowed(policy, ConnectorRecoveryAction.RETRY):
            delay = 60 if failure.failure_type == ConnectorFailureType.RATE_LIMIT else 10
            return _stamp_receipt(_receipt(failure, ConnectorRecoveryAction.RETRY, ConnectorHealingStatus.RETRY_SCHEDULED, False, delay, "", ("retry_budget", "idempotency_key", "verification_after_retry"), evidence_refs, {"attempt_count": attempt_count}))
        if _allowed(policy, ConnectorRecoveryAction.SWITCH_PROVIDER) and policy.fallback_providers:
            return _stamp_receipt(_receipt(failure, ConnectorRecoveryAction.SWITCH_PROVIDER, ConnectorHealingStatus.PROVIDER_SWITCH_REQUIRED, False, 0, policy.fallback_providers[0], ("fallback_provider_certification", "fresh_connector_receipt"), evidence_refs, {"original_provider": failure.provider}))
        if not write_operation and _allowed(policy, ConnectorRecoveryAction.DEGRADE_READ_ONLY):
            return _stamp_receipt(_receipt(failure, ConnectorRecoveryAction.DEGRADE_READ_ONLY, ConnectorHealingStatus.DEGRADED_READ_ONLY, True, 0, "", ("read_only_scope", "operator_notice"), evidence_refs, {"degraded_mode": "read_only"}))
        return _stamp_receipt(_receipt(failure, ConnectorRecoveryAction.OPEN_INCIDENT, ConnectorHealingStatus.INCIDENT_OPENED, False, 0, "", ("operator_review", policy.incident_queue), evidence_refs, {}))

    def _receipt_missing(self, failure: ConnectorFailure, policy: ConnectorRecoveryPolicy, evidence_refs: tuple[str, ...]) -> ConnectorHealingReceipt:
        if _allowed(policy, ConnectorRecoveryAction.REVOKE_CAPABILITY):
            return _stamp_receipt(_receipt(failure, ConnectorRecoveryAction.REVOKE_CAPABILITY, ConnectorHealingStatus.CAPABILITY_REVOKED, False, 0, "", ("receipt_restoration", "operator_review"), evidence_refs, {"revoked_until_receipt_restored": True}))
        return _stamp_receipt(_receipt(failure, ConnectorRecoveryAction.REQUIRE_REVIEW, ConnectorHealingStatus.REQUIRES_REVIEW, False, 0, "", ("missing_receipt_review",), evidence_refs, {}))

    def _unsafe_or_auth_failure(self, failure: ConnectorFailure, policy: ConnectorRecoveryPolicy, evidence_refs: tuple[str, ...]) -> ConnectorHealingReceipt:
        if _allowed(policy, ConnectorRecoveryAction.REVOKE_CAPABILITY):
            return _stamp_receipt(_receipt(failure, ConnectorRecoveryAction.REVOKE_CAPABILITY, ConnectorHealingStatus.CAPABILITY_REVOKED, False, 0, "", ("credential_rotation", "operator_review"), evidence_refs, {"unsafe_or_auth_failure": True}))
        return _stamp_receipt(_receipt(failure, ConnectorRecoveryAction.OPEN_INCIDENT, ConnectorHealingStatus.INCIDENT_OPENED, False, 0, "", ("credential_rotation",), evidence_refs, {}))


def _receipt(failure: ConnectorFailure, action: ConnectorRecoveryAction, status: ConnectorHealingStatus, safe_to_continue: bool, retry_after_seconds: int, fallback_provider: str, required_controls: tuple[str, ...], evidence_refs: tuple[str, ...], metadata: dict[str, Any]) -> ConnectorHealingReceipt:
    return ConnectorHealingReceipt(
        receipt_id=f"healing-{failure.failure_id}",
        connector_id=failure.connector_id,
        tenant_id=failure.tenant_id,
        failure_id=failure.failure_id,
        action=action,
        status=status,
        safe_to_continue=safe_to_continue,
        retry_after_seconds=retry_after_seconds,
        fallback_provider=fallback_provider,
        required_controls=required_controls,
        evidence_refs=evidence_refs,
        metadata={"provider": failure.provider, "operation": failure.operation, "failure_type": failure.failure_type.value, **metadata},
    )


def _stamp_receipt(receipt: ConnectorHealingReceipt) -> ConnectorHealingReceipt:
    stamped = replace(receipt, receipt_hash="")
    return replace(stamped, receipt_hash=canonical_hash(asdict(stamped)))


def _receipt_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload = dict(metadata)
    payload["provider_success_not_assumed"] = True
    payload["policy_declared_recovery_action"] = True
    payload["verification_required_after_recovery"] = True
    payload["healing_receipt_is_not_terminal_closure"] = True
    return payload


def _allowed(policy: ConnectorRecoveryPolicy, action: ConnectorRecoveryAction) -> bool:
    return action in policy.allowed_actions


def _combined_refs(*groups: tuple[str, ...]) -> tuple[str, ...]:
    refs: list[str] = []
    for group in groups:
        refs.extend(group)
    return tuple(dict.fromkeys(ref for ref in refs if str(ref).strip()))


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    return value
