"""Purpose: canonical provider configuration and credential scope contracts.
Governance scope: provider management contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Every provider carries explicit identity, class, and credential scope.
  - Credential secrets MUST NOT appear in contracts.
  - Provider health is tracked from invocation results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class ProviderClass(StrEnum):
    INTEGRATION = "integration"
    COMMUNICATION = "communication"
    MODEL = "model"


class ProviderHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CredentialScope(ContractRecord):
    """Declared permission boundary of a provider's credentials."""

    scope_id: str
    provider_id: str
    allowed_base_urls: tuple[str, ...] = ()
    allowed_operations: tuple[str, ...] = ()
    rate_limit_per_minute: int | None = None
    cost_limit_per_invocation: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope_id", require_non_empty_text(self.scope_id, "scope_id"))
        object.__setattr__(self, "provider_id", require_non_empty_text(self.provider_id, "provider_id"))
        if self.rate_limit_per_minute is not None:
            if not isinstance(self.rate_limit_per_minute, int) or self.rate_limit_per_minute <= 0:
                raise ValueError("rate_limit_per_minute must be a positive integer")
        if self.cost_limit_per_invocation is not None:
            if not isinstance(self.cost_limit_per_invocation, (int, float)) or self.cost_limit_per_invocation <= 0:
                raise ValueError("cost_limit_per_invocation must be a positive number")


@dataclass(frozen=True, slots=True)
class ProviderDescriptor(ContractRecord):
    """Identity, class, and configuration of a registered provider."""

    provider_id: str
    name: str
    provider_class: ProviderClass
    credential_scope_id: str
    enabled: bool
    base_url: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("provider_id", "name", "credential_scope_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.provider_class, ProviderClass):
            raise ValueError("provider_class must be a ProviderClass value")
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        if self.base_url is not None:
            object.__setattr__(self, "base_url", require_non_empty_text(self.base_url, "base_url"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ProviderHealthRecord(ContractRecord):
    """Current health/availability state of a provider."""

    provider_id: str
    status: ProviderHealthStatus
    last_checked_at: str
    reason: str
    consecutive_failures: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", require_non_empty_text(self.provider_id, "provider_id"))
        if not isinstance(self.status, ProviderHealthStatus):
            raise ValueError("status must be a ProviderHealthStatus value")
        object.__setattr__(self, "last_checked_at", require_datetime_text(self.last_checked_at, "last_checked_at"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        if not isinstance(self.consecutive_failures, int) or self.consecutive_failures < 0:
            raise ValueError("consecutive_failures must be a non-negative integer")
