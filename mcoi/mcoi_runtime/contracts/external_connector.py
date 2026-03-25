"""Purpose: external connector runtime contracts.
Governance scope: typed descriptors, auth modes, health states, rate limits,
    quotas, execution records, capability bindings, failure records, fallback
    chains, secret scopes, and compliance policies for live external connectivity.
Dependencies: _base contract utilities.
Invariants:
  - Every connector declares its type, auth mode, and capability binding.
  - All outputs are frozen and immutable.
  - Reliability scores are unit floats [0.0, 1.0].
  - Rate limits and quotas are non-negative integers.
  - Failure records are explicitly typed with recovery hints.
  - Secret scopes enforce rotation and retention.
  - Redaction policies govern stored payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExternalConnectorType(Enum):
    """Classification of external connector."""
    SMS_PROVIDER = "sms_provider"
    CHAT_PROVIDER = "chat_provider"
    VOICE_PROVIDER = "voice_provider"
    EMAIL_PROVIDER = "email_provider"
    WEBHOOK_PROVIDER = "webhook_provider"
    SOCIAL_PROVIDER = "social_provider"
    STORAGE_PROVIDER = "storage_provider"
    PARSER_PROVIDER = "parser_provider"
    GENERIC_API = "generic_api"


class ConnectorAuthMode(Enum):
    """Authentication mode for a connector."""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC_AUTH = "basic_auth"
    BEARER_TOKEN = "bearer_token"
    MUTUAL_TLS = "mutual_tls"
    HMAC_SIGNATURE = "hmac_signature"
    NONE = "none"


class ConnectorHealthState(Enum):
    """Operational health state of a connector."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    CIRCUIT_OPEN = "circuit_open"


class ConnectorFailureCategory(Enum):
    """Category of connector failure."""
    AUTH_FAILURE = "auth_failure"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    PROVIDER_ERROR = "provider_error"
    PAYLOAD_REJECTED = "payload_rejected"
    POLICY_BLOCKED = "policy_blocked"
    CIRCUIT_BROKEN = "circuit_broken"
    UNKNOWN = "unknown"


class SecretRotationState(Enum):
    """State of credential rotation lifecycle."""
    CURRENT = "current"
    PENDING_ROTATION = "pending_rotation"
    ROTATING = "rotating"
    EXPIRED = "expired"
    REVOKED = "revoked"


class RedactionLevel(Enum):
    """Redaction level for stored payloads."""
    NONE = "none"
    HEADERS_ONLY = "headers_only"
    BODY_PARTIAL = "body_partial"
    BODY_FULL = "body_full"
    COMPLETE = "complete"


class FallbackStrategy(Enum):
    """Strategy for fallback provider selection."""
    PRIORITY_ORDER = "priority_order"
    ROUND_ROBIN = "round_robin"
    LEAST_FAILURES = "least_failures"
    LOWEST_LATENCY = "lowest_latency"
    CAPABILITY_MATCH = "capability_match"


class ConsentState(Enum):
    """Consent / eligibility state for a channel-identity binding."""
    GRANTED = "granted"
    DENIED = "denied"
    PENDING = "pending"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConnectorRateLimitPolicy(ContractRecord):
    """Rate limit policy for an external connector."""

    policy_id: str = ""
    connector_id: str = ""
    max_requests_per_second: int = 0
    max_requests_per_minute: int = 0
    max_requests_per_hour: int = 0
    max_burst_size: int = 0
    retry_after_seconds: int = 30
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "policy_id",
            require_non_empty_text(self.policy_id, "policy_id"),
        )
        object.__setattr__(
            self, "connector_id",
            require_non_empty_text(self.connector_id, "connector_id"),
        )
        object.__setattr__(
            self, "max_requests_per_second",
            require_non_negative_int(self.max_requests_per_second, "max_requests_per_second"),
        )
        object.__setattr__(
            self, "max_requests_per_minute",
            require_non_negative_int(self.max_requests_per_minute, "max_requests_per_minute"),
        )
        object.__setattr__(
            self, "max_requests_per_hour",
            require_non_negative_int(self.max_requests_per_hour, "max_requests_per_hour"),
        )
        object.__setattr__(
            self, "max_burst_size",
            require_non_negative_int(self.max_burst_size, "max_burst_size"),
        )
        object.__setattr__(
            self, "retry_after_seconds",
            require_non_negative_int(self.retry_after_seconds, "retry_after_seconds"),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ConnectorQuotaState(ContractRecord):
    """Point-in-time quota state for a connector."""

    quota_id: str = ""
    connector_id: str = ""
    quota_limit: int = 0
    quota_used: int = 0
    quota_remaining: int = 0
    reset_at: str = ""
    reported_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "quota_id",
            require_non_empty_text(self.quota_id, "quota_id"),
        )
        object.__setattr__(
            self, "connector_id",
            require_non_empty_text(self.connector_id, "connector_id"),
        )
        object.__setattr__(
            self, "quota_limit",
            require_non_negative_int(self.quota_limit, "quota_limit"),
        )
        object.__setattr__(
            self, "quota_used",
            require_non_negative_int(self.quota_used, "quota_used"),
        )
        object.__setattr__(
            self, "quota_remaining",
            require_non_negative_int(self.quota_remaining, "quota_remaining"),
        )
        require_datetime_text(self.reset_at, "reset_at")
        require_datetime_text(self.reported_at, "reported_at")


@dataclass(frozen=True, slots=True)
class ConnectorExecutionRecord(ContractRecord):
    """Record of a single connector execution (send/receive/parse)."""

    execution_id: str = ""
    connector_id: str = ""
    connector_type: ExternalConnectorType = ExternalConnectorType.GENERIC_API
    operation: str = ""
    success: bool = True
    latency_ms: float = 0.0
    request_bytes: int = 0
    response_bytes: int = 0
    status_code: int = 0
    error_message: str = ""
    correlation_id: str = ""
    executed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "execution_id",
            require_non_empty_text(self.execution_id, "execution_id"),
        )
        object.__setattr__(
            self, "connector_id",
            require_non_empty_text(self.connector_id, "connector_id"),
        )
        if not isinstance(self.connector_type, ExternalConnectorType):
            raise ValueError("connector_type must be an ExternalConnectorType")
        object.__setattr__(
            self, "operation",
            require_non_empty_text(self.operation, "operation"),
        )
        if not isinstance(self.success, bool):
            raise ValueError("success must be a boolean")
        object.__setattr__(
            self, "latency_ms",
            require_non_negative_float(self.latency_ms, "latency_ms"),
        )
        object.__setattr__(
            self, "request_bytes",
            require_non_negative_int(self.request_bytes, "request_bytes"),
        )
        object.__setattr__(
            self, "response_bytes",
            require_non_negative_int(self.response_bytes, "response_bytes"),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
        require_datetime_text(self.executed_at, "executed_at")


@dataclass(frozen=True, slots=True)
class ConnectorCapabilityBinding(ContractRecord):
    """Binds a connector to a channel adapter or artifact parser capability."""

    binding_id: str = ""
    connector_id: str = ""
    connector_type: ExternalConnectorType = ExternalConnectorType.GENERIC_API
    bound_adapter_id: str = ""
    bound_parser_id: str = ""
    supported_operations: tuple[str, ...] = ()
    max_payload_bytes: int = 0
    reliability_score: float = 1.0
    priority: int = 0
    enabled: bool = True
    tags: tuple[str, ...] = ()
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "binding_id",
            require_non_empty_text(self.binding_id, "binding_id"),
        )
        object.__setattr__(
            self, "connector_id",
            require_non_empty_text(self.connector_id, "connector_id"),
        )
        if not isinstance(self.connector_type, ExternalConnectorType):
            raise ValueError("connector_type must be an ExternalConnectorType")
        object.__setattr__(
            self, "supported_operations",
            freeze_value(list(self.supported_operations)),
        )
        object.__setattr__(
            self, "max_payload_bytes",
            require_non_negative_int(self.max_payload_bytes, "max_payload_bytes"),
        )
        object.__setattr__(
            self, "reliability_score",
            require_unit_float(self.reliability_score, "reliability_score"),
        )
        object.__setattr__(
            self, "priority",
            require_non_negative_int(self.priority, "priority"),
        )
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        object.__setattr__(
            self, "tags",
            freeze_value(list(self.tags)),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ConnectorFailureRecord(ContractRecord):
    """Record of a connector failure with typed category and recovery hints."""

    failure_id: str = ""
    connector_id: str = ""
    category: ConnectorFailureCategory = ConnectorFailureCategory.UNKNOWN
    operation: str = ""
    error_message: str = ""
    status_code: int = 0
    is_retriable: bool = True
    retry_after_seconds: int = 0
    fallback_connector_id: str = ""
    correlation_id: str = ""
    occurred_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "failure_id",
            require_non_empty_text(self.failure_id, "failure_id"),
        )
        object.__setattr__(
            self, "connector_id",
            require_non_empty_text(self.connector_id, "connector_id"),
        )
        if not isinstance(self.category, ConnectorFailureCategory):
            raise ValueError("category must be a ConnectorFailureCategory")
        object.__setattr__(
            self, "operation",
            require_non_empty_text(self.operation, "operation"),
        )
        if not isinstance(self.is_retriable, bool):
            raise ValueError("is_retriable must be a boolean")
        object.__setattr__(
            self, "retry_after_seconds",
            require_non_negative_int(self.retry_after_seconds, "retry_after_seconds"),
        )
        require_datetime_text(self.occurred_at, "occurred_at")


@dataclass(frozen=True, slots=True)
class SecretScope(ContractRecord):
    """Scoped credential binding for a connector."""

    scope_id: str = ""
    connector_id: str = ""
    auth_mode: ConnectorAuthMode = ConnectorAuthMode.NONE
    rotation_state: SecretRotationState = SecretRotationState.CURRENT
    credential_ref: str = ""
    rotation_interval_hours: int = 0
    last_rotated_at: str = ""
    expires_at: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "scope_id",
            require_non_empty_text(self.scope_id, "scope_id"),
        )
        object.__setattr__(
            self, "connector_id",
            require_non_empty_text(self.connector_id, "connector_id"),
        )
        if not isinstance(self.auth_mode, ConnectorAuthMode):
            raise ValueError("auth_mode must be a ConnectorAuthMode")
        if not isinstance(self.rotation_state, SecretRotationState):
            raise ValueError("rotation_state must be a SecretRotationState")
        object.__setattr__(
            self, "credential_ref",
            require_non_empty_text(self.credential_ref, "credential_ref"),
        )
        object.__setattr__(
            self, "rotation_interval_hours",
            require_non_negative_int(self.rotation_interval_hours, "rotation_interval_hours"),
        )
        require_datetime_text(self.last_rotated_at, "last_rotated_at")
        require_datetime_text(self.expires_at, "expires_at")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ConnectorRetentionPolicy(ContractRecord):
    """Retention and redaction policy for connector payloads."""

    policy_id: str = ""
    connector_id: str = ""
    redaction_level: RedactionLevel = RedactionLevel.NONE
    retention_days: int = 90
    store_request_payload: bool = False
    store_response_payload: bool = False
    pii_scrub_enabled: bool = True
    audit_trail_required: bool = True
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "policy_id",
            require_non_empty_text(self.policy_id, "policy_id"),
        )
        object.__setattr__(
            self, "connector_id",
            require_non_empty_text(self.connector_id, "connector_id"),
        )
        if not isinstance(self.redaction_level, RedactionLevel):
            raise ValueError("redaction_level must be a RedactionLevel")
        object.__setattr__(
            self, "retention_days",
            require_non_negative_int(self.retention_days, "retention_days"),
        )
        if not isinstance(self.store_request_payload, bool):
            raise ValueError("store_request_payload must be a boolean")
        if not isinstance(self.store_response_payload, bool):
            raise ValueError("store_response_payload must be a boolean")
        if not isinstance(self.pii_scrub_enabled, bool):
            raise ValueError("pii_scrub_enabled must be a boolean")
        if not isinstance(self.audit_trail_required, bool):
            raise ValueError("audit_trail_required must be a boolean")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ConnectorHealthSnapshot(ContractRecord):
    """Point-in-time health snapshot for a connector."""

    snapshot_id: str = ""
    connector_id: str = ""
    health_state: ConnectorHealthState = ConnectorHealthState.UNKNOWN
    reliability_score: float = 1.0
    total_executions: int = 0
    failed_executions: int = 0
    avg_latency_ms: float = 0.0
    circuit_breaker_trips: int = 0
    consecutive_failures: int = 0
    last_success_at: str = ""
    last_failure_at: str = ""
    reported_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "snapshot_id",
            require_non_empty_text(self.snapshot_id, "snapshot_id"),
        )
        object.__setattr__(
            self, "connector_id",
            require_non_empty_text(self.connector_id, "connector_id"),
        )
        if not isinstance(self.health_state, ConnectorHealthState):
            raise ValueError("health_state must be a ConnectorHealthState")
        object.__setattr__(
            self, "reliability_score",
            require_unit_float(self.reliability_score, "reliability_score"),
        )
        object.__setattr__(
            self, "total_executions",
            require_non_negative_int(self.total_executions, "total_executions"),
        )
        object.__setattr__(
            self, "failed_executions",
            require_non_negative_int(self.failed_executions, "failed_executions"),
        )
        object.__setattr__(
            self, "avg_latency_ms",
            require_non_negative_float(self.avg_latency_ms, "avg_latency_ms"),
        )
        object.__setattr__(
            self, "circuit_breaker_trips",
            require_non_negative_int(self.circuit_breaker_trips, "circuit_breaker_trips"),
        )
        object.__setattr__(
            self, "consecutive_failures",
            require_non_negative_int(self.consecutive_failures, "consecutive_failures"),
        )
        require_datetime_text(self.reported_at, "reported_at")


@dataclass(frozen=True, slots=True)
class FallbackChainEntry(ContractRecord):
    """Entry in a fallback chain for provider selection."""

    entry_id: str = ""
    chain_id: str = ""
    connector_id: str = ""
    priority: int = 0
    min_reliability: float = 0.0
    max_latency_ms: float = 0.0
    enabled: bool = True
    conditions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "entry_id",
            require_non_empty_text(self.entry_id, "entry_id"),
        )
        object.__setattr__(
            self, "chain_id",
            require_non_empty_text(self.chain_id, "chain_id"),
        )
        object.__setattr__(
            self, "connector_id",
            require_non_empty_text(self.connector_id, "connector_id"),
        )
        object.__setattr__(
            self, "priority",
            require_non_negative_int(self.priority, "priority"),
        )
        object.__setattr__(
            self, "min_reliability",
            require_unit_float(self.min_reliability, "min_reliability"),
        )
        object.__setattr__(
            self, "max_latency_ms",
            require_non_negative_float(self.max_latency_ms, "max_latency_ms"),
        )
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        object.__setattr__(
            self, "conditions",
            freeze_value(dict(self.conditions)),
        )


@dataclass(frozen=True, slots=True)
class FallbackChain(ContractRecord):
    """Ordered fallback chain for provider selection."""

    chain_id: str = ""
    name: str = ""
    strategy: FallbackStrategy = FallbackStrategy.PRIORITY_ORDER
    entries: tuple[FallbackChainEntry, ...] = ()
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "chain_id",
            require_non_empty_text(self.chain_id, "chain_id"),
        )
        object.__setattr__(
            self, "name",
            require_non_empty_text(self.name, "name"),
        )
        if not isinstance(self.strategy, FallbackStrategy):
            raise ValueError("strategy must be a FallbackStrategy")
        object.__setattr__(
            self, "entries",
            freeze_value(list(self.entries)),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ChannelConsentRecord(ContractRecord):
    """Consent / eligibility record binding identity to channel."""

    consent_id: str = ""
    identity_id: str = ""
    channel_type: str = ""
    connector_id: str = ""
    consent_state: ConsentState = ConsentState.PENDING
    granted_at: str = ""
    expires_at: str = ""
    recorded_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "consent_id",
            require_non_empty_text(self.consent_id, "consent_id"),
        )
        object.__setattr__(
            self, "identity_id",
            require_non_empty_text(self.identity_id, "identity_id"),
        )
        object.__setattr__(
            self, "channel_type",
            require_non_empty_text(self.channel_type, "channel_type"),
        )
        object.__setattr__(
            self, "connector_id",
            require_non_empty_text(self.connector_id, "connector_id"),
        )
        if not isinstance(self.consent_state, ConsentState):
            raise ValueError("consent_state must be a ConsentState")
        require_datetime_text(self.recorded_at, "recorded_at")


@dataclass(frozen=True, slots=True)
class ExternalConnectorDescriptor(ContractRecord):
    """Full descriptor for a registered external connector."""

    connector_id: str = ""
    name: str = ""
    connector_type: ExternalConnectorType = ExternalConnectorType.GENERIC_API
    auth_mode: ConnectorAuthMode = ConnectorAuthMode.NONE
    health_state: ConnectorHealthState = ConnectorHealthState.UNKNOWN
    provider_name: str = ""
    version: str = "1.0.0"
    base_url: str = ""
    bound_adapter_id: str = ""
    bound_parser_id: str = ""
    reliability_score: float = 1.0
    enabled: bool = True
    tags: tuple[str, ...] = ()
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "connector_id",
            require_non_empty_text(self.connector_id, "connector_id"),
        )
        object.__setattr__(
            self, "name",
            require_non_empty_text(self.name, "name"),
        )
        if not isinstance(self.connector_type, ExternalConnectorType):
            raise ValueError("connector_type must be an ExternalConnectorType")
        if not isinstance(self.auth_mode, ConnectorAuthMode):
            raise ValueError("auth_mode must be a ConnectorAuthMode")
        if not isinstance(self.health_state, ConnectorHealthState):
            raise ValueError("health_state must be a ConnectorHealthState")
        object.__setattr__(
            self, "provider_name",
            require_non_empty_text(self.provider_name, "provider_name"),
        )
        object.__setattr__(
            self, "version",
            require_non_empty_text(self.version, "version"),
        )
        object.__setattr__(
            self, "reliability_score",
            require_unit_float(self.reliability_score, "reliability_score"),
        )
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        object.__setattr__(
            self, "tags",
            freeze_value(list(self.tags)),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
        require_datetime_text(self.created_at, "created_at")
