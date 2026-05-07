"""Purpose: provider registry — registration, health tracking, scope enforcement.
Governance scope: provider management core logic only.
Dependencies: provider contracts, invariant helpers.
Invariants:
  - Providers must be registered before invocation.
  - Disabled/unavailable providers MUST NOT be invoked.
  - Credential scope is enforced at invocation time.
  - Health is updated from invocation results, not assumed.
"""

from __future__ import annotations

from typing import Callable

from mcoi_runtime.contracts.provider import (
    CredentialScope,
    ProviderClass,
    ProviderDescriptor,
    ProviderHealthRecord,
    ProviderHealthStatus,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text


class ProviderRegistry:
    """Central registry for all external providers with health tracking and scope enforcement."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._providers: dict[str, ProviderDescriptor] = {}
        self._scopes: dict[str, CredentialScope] = {}
        self._health: dict[str, ProviderHealthRecord] = {}

    def register(
        self,
        descriptor: ProviderDescriptor,
        scope: CredentialScope,
    ) -> ProviderDescriptor:
        if descriptor.provider_id in self._providers:
            raise RuntimeCoreInvariantError("provider already registered")
        if scope.provider_id != descriptor.provider_id:
            raise RuntimeCoreInvariantError("credential scope provider_id must match descriptor")
        if scope.scope_id != descriptor.credential_scope_id:
            raise RuntimeCoreInvariantError("credential scope_id must match descriptor credential_scope_id")
        self._providers[descriptor.provider_id] = descriptor
        self._scopes[descriptor.provider_id] = scope
        self._health[descriptor.provider_id] = ProviderHealthRecord(
            provider_id=descriptor.provider_id,
            status=ProviderHealthStatus.UNKNOWN,
            last_checked_at=self._clock(),
            reason="initial_registration",
        )
        return descriptor

    def get_provider(self, provider_id: str) -> ProviderDescriptor | None:
        ensure_non_empty_text("provider_id", provider_id)
        return self._providers.get(provider_id)

    def get_scope(self, provider_id: str) -> CredentialScope | None:
        ensure_non_empty_text("provider_id", provider_id)
        return self._scopes.get(provider_id)

    def get_health(self, provider_id: str) -> ProviderHealthRecord | None:
        ensure_non_empty_text("provider_id", provider_id)
        return self._health.get(provider_id)

    def list_providers(
        self,
        *,
        provider_class: ProviderClass | None = None,
        enabled_only: bool = False,
    ) -> tuple[ProviderDescriptor, ...]:
        providers = sorted(self._providers.values(), key=lambda p: p.provider_id)
        if provider_class is not None:
            providers = [p for p in providers if p.provider_class == provider_class]
        if enabled_only:
            providers = [p for p in providers if p.enabled]
        return tuple(providers)

    def check_invocable(self, provider_id: str) -> tuple[bool, str]:
        """Check if a provider can be invoked. Returns (ok, reason)."""
        ensure_non_empty_text("provider_id", provider_id)
        provider = self._providers.get(provider_id)
        if provider is None:
            return False, "provider_not_registered"
        if not provider.enabled:
            return False, "provider_disabled"
        health = self._health.get(provider_id)
        if health and health.status is ProviderHealthStatus.UNAVAILABLE:
            return False, "provider_unavailable"
        return True, "ok"

    def check_url_in_scope(self, provider_id: str, url: str) -> bool:
        """Check if a URL falls within the provider's allowed base URLs."""
        scope = self._scopes.get(provider_id)
        if scope is None:
            return False
        if not scope.allowed_base_urls:
            return True  # No URL restrictions
        return any(url.startswith(base) for base in scope.allowed_base_urls)

    def record_success(self, provider_id: str) -> ProviderHealthRecord:
        """Record a successful invocation — update health to healthy."""
        ensure_non_empty_text("provider_id", provider_id)
        record = ProviderHealthRecord(
            provider_id=provider_id,
            status=ProviderHealthStatus.HEALTHY,
            last_checked_at=self._clock(),
            reason="invocation_succeeded",
            consecutive_failures=0,
        )
        self._health[provider_id] = record
        return record

    def record_failure(self, provider_id: str, reason: str) -> ProviderHealthRecord:
        """Record a failed invocation — update health, track consecutive failures."""
        ensure_non_empty_text("provider_id", provider_id)
        ensure_non_empty_text("reason", reason)
        existing = self._health.get(provider_id)
        failures = (existing.consecutive_failures + 1) if existing else 1
        status = ProviderHealthStatus.DEGRADED if failures < 3 else ProviderHealthStatus.UNAVAILABLE
        record = ProviderHealthRecord(
            provider_id=provider_id,
            status=status,
            last_checked_at=self._clock(),
            reason=reason,
            consecutive_failures=failures,
        )
        self._health[provider_id] = record
        return record
