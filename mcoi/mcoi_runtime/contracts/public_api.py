"""Purpose: public API / product surface runtime contracts.
Governance scope: typed descriptors for API requests, responses,
    endpoints, errors, rate limits, idempotency, snapshots,
    violations, assessments, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every request references a tenant.
  - Rate limits are non-negative.
  - All outputs are frozen.
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


class ApiStatus(Enum):
    """Status of an API request or endpoint."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    RETIRED = "retired"


class EndpointKind(Enum):
    """Kind of API endpoint."""
    READ = "read"
    WRITE = "write"
    MUTATION = "mutation"
    QUERY = "query"
    HEALTH = "health"


class RequestDisposition(Enum):
    """Disposition of an API request."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RATE_LIMITED = "rate_limited"
    DEDUPLICATED = "deduplicated"


class AuthDisposition(Enum):
    """Disposition of an authentication check."""
    AUTHENTICATED = "authenticated"
    DENIED = "denied"
    EXPIRED = "expired"
    INVALID = "invalid"


class RateLimitDisposition(Enum):
    """Disposition of a rate limit check."""
    ALLOWED = "allowed"
    THROTTLED = "throttled"
    BLOCKED = "blocked"
    EXEMPT = "exempt"


class ApiVisibility(Enum):
    """Visibility of an API endpoint."""
    PUBLIC = "public"
    PARTNER = "partner"
    INTERNAL = "internal"
    ADMIN = "admin"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ApiRequest(ContractRecord):
    """An incoming API request."""

    request_id: str = ""
    tenant_id: str = ""
    endpoint_id: str = ""
    caller_ref: str = ""
    disposition: RequestDisposition = RequestDisposition.ACCEPTED
    auth_disposition: AuthDisposition = AuthDisposition.AUTHENTICATED
    idempotency_key: str = ""
    received_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "endpoint_id", require_non_empty_text(self.endpoint_id, "endpoint_id"))
        object.__setattr__(self, "caller_ref", require_non_empty_text(self.caller_ref, "caller_ref"))
        if not isinstance(self.disposition, RequestDisposition):
            raise ValueError("disposition must be a RequestDisposition")
        if not isinstance(self.auth_disposition, AuthDisposition):
            raise ValueError("auth_disposition must be an AuthDisposition")
        object.__setattr__(self, "idempotency_key", require_non_empty_text(self.idempotency_key, "idempotency_key"))
        require_datetime_text(self.received_at, "received_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ApiResponse(ContractRecord):
    """An API response."""

    response_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    status_code: int = 200
    disposition: RequestDisposition = RequestDisposition.ACCEPTED
    payload_ref: str = ""
    responded_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "response_id", require_non_empty_text(self.response_id, "response_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "status_code", require_non_negative_int(self.status_code, "status_code"))
        if not isinstance(self.disposition, RequestDisposition):
            raise ValueError("disposition must be a RequestDisposition")
        object.__setattr__(self, "payload_ref", require_non_empty_text(self.payload_ref, "payload_ref"))
        require_datetime_text(self.responded_at, "responded_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EndpointDescriptor(ContractRecord):
    """A registered API endpoint."""

    endpoint_id: str = ""
    tenant_id: str = ""
    path: str = ""
    kind: EndpointKind = EndpointKind.READ
    visibility: ApiVisibility = ApiVisibility.PUBLIC
    status: ApiStatus = ApiStatus.ACTIVE
    target_runtime: str = ""
    target_action: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "endpoint_id", require_non_empty_text(self.endpoint_id, "endpoint_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "path", require_non_empty_text(self.path, "path"))
        if not isinstance(self.kind, EndpointKind):
            raise ValueError("kind must be an EndpointKind")
        if not isinstance(self.visibility, ApiVisibility):
            raise ValueError("visibility must be an ApiVisibility")
        if not isinstance(self.status, ApiStatus):
            raise ValueError("status must be an ApiStatus")
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        object.__setattr__(self, "target_action", require_non_empty_text(self.target_action, "target_action"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ApiErrorRecord(ContractRecord):
    """An API error record."""

    error_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    error_code: str = ""
    error_message: str = ""
    status_code: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "error_id", require_non_empty_text(self.error_id, "error_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "error_code", require_non_empty_text(self.error_code, "error_code"))
        object.__setattr__(self, "error_message", require_non_empty_text(self.error_message, "error_message"))
        object.__setattr__(self, "status_code", require_non_negative_int(self.status_code, "status_code"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RateLimitRecord(ContractRecord):
    """A rate limit check record."""

    limit_id: str = ""
    tenant_id: str = ""
    caller_ref: str = ""
    endpoint_id: str = ""
    disposition: RateLimitDisposition = RateLimitDisposition.ALLOWED
    requests_remaining: int = 0
    window_reset_at: str = ""
    checked_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "limit_id", require_non_empty_text(self.limit_id, "limit_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "caller_ref", require_non_empty_text(self.caller_ref, "caller_ref"))
        object.__setattr__(self, "endpoint_id", require_non_empty_text(self.endpoint_id, "endpoint_id"))
        if not isinstance(self.disposition, RateLimitDisposition):
            raise ValueError("disposition must be a RateLimitDisposition")
        object.__setattr__(self, "requests_remaining", require_non_negative_int(self.requests_remaining, "requests_remaining"))
        require_datetime_text(self.window_reset_at, "window_reset_at")
        require_datetime_text(self.checked_at, "checked_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class IdempotencyRecord(ContractRecord):
    """An idempotency check record."""

    idempotency_key: str = ""
    request_id: str = ""
    tenant_id: str = ""
    endpoint_id: str = ""
    original_response_id: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "idempotency_key", require_non_empty_text(self.idempotency_key, "idempotency_key"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "endpoint_id", require_non_empty_text(self.endpoint_id, "endpoint_id"))
        object.__setattr__(self, "original_response_id", require_non_empty_text(self.original_response_id, "original_response_id"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ApiSnapshot(ContractRecord):
    """Point-in-time snapshot of API state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_endpoints: int = 0
    active_endpoints: int = 0
    total_requests: int = 0
    accepted_requests: int = 0
    rejected_requests: int = 0
    rate_limited_requests: int = 0
    deduplicated_requests: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_endpoints", require_non_negative_int(self.total_endpoints, "total_endpoints"))
        object.__setattr__(self, "active_endpoints", require_non_negative_int(self.active_endpoints, "active_endpoints"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "accepted_requests", require_non_negative_int(self.accepted_requests, "accepted_requests"))
        object.__setattr__(self, "rejected_requests", require_non_negative_int(self.rejected_requests, "rejected_requests"))
        object.__setattr__(self, "rate_limited_requests", require_non_negative_int(self.rate_limited_requests, "rate_limited_requests"))
        object.__setattr__(self, "deduplicated_requests", require_non_negative_int(self.deduplicated_requests, "deduplicated_requests"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ApiViolation(ContractRecord):
    """An API violation."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ApiAssessment(ContractRecord):
    """An assessment of API health."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_endpoints: int = 0
    active_endpoints: int = 0
    availability_score: float = 0.0
    error_rate: float = 0.0
    total_violations: int = 0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_endpoints", require_non_negative_int(self.total_endpoints, "total_endpoints"))
        object.__setattr__(self, "active_endpoints", require_non_negative_int(self.active_endpoints, "active_endpoints"))
        object.__setattr__(self, "availability_score", require_unit_float(self.availability_score, "availability_score"))
        object.__setattr__(self, "error_rate", require_unit_float(self.error_rate, "error_rate"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ApiClosureReport(ContractRecord):
    """Closure report for API surface."""

    report_id: str = ""
    tenant_id: str = ""
    total_endpoints: int = 0
    total_requests: int = 0
    total_responses: int = 0
    total_errors: int = 0
    total_rate_limits: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_endpoints", require_non_negative_int(self.total_endpoints, "total_endpoints"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_responses", require_non_negative_int(self.total_responses, "total_responses"))
        object.__setattr__(self, "total_errors", require_non_negative_int(self.total_errors, "total_errors"))
        object.__setattr__(self, "total_rate_limits", require_non_negative_int(self.total_rate_limits, "total_rate_limits"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
