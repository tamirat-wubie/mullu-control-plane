"""Purpose: provider attribution ledger for per-operation provider-plane identity.
Governance scope: deterministic attribution of provider ids to runtime operations.
Dependencies: provider attribution contracts, provider registry, and invariant helpers.
Invariants:
  - Only enabled, healthy, registered providers can be attributed through plane resolution.
  - Each operation/provider-class pair has at most one attribution record.
  - Ledger mutation is append-only for new attribution identities.
  - Attribution exposes source and evidence id instead of implying hidden invocation facts.
"""

from __future__ import annotations

from typing import Callable

from mcoi_runtime.contracts.provider import ProviderClass, ProviderHealthStatus
from mcoi_runtime.contracts.provider_attribution import (
    ProviderAttribution,
    ProviderAttributionSource,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier
from mcoi_runtime.core.provider_registry import ProviderRegistry


class ProviderAttributionLedger:
    """Append-only provider attribution ledger for runtime operations."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._records: dict[str, ProviderAttribution] = {}
        self._operation_index: dict[str, tuple[str, ...]] = {}

    @property
    def attribution_count(self) -> int:
        """Return the number of attribution records."""
        return len(self._records)

    def list_for_operation(self, operation_id: str) -> tuple[ProviderAttribution, ...]:
        """Return records for an operation in provider-class order."""
        ensure_non_empty_text("operation_id", operation_id)
        attribution_ids = self._operation_index.get(operation_id, ())
        return tuple(self._records[attribution_id] for attribution_id in attribution_ids)

    def attribute_healthy_planes(
        self,
        *,
        request_id: str,
        operation_id: str,
        execution_id: str | None,
        provider_registry: ProviderRegistry,
    ) -> tuple[ProviderAttribution, ...]:
        """Attribute the first healthy enabled provider for each provider plane.

        The source explicitly says this is a healthy-plane resolution record, not
        a routed invocation receipt.
        """
        ensure_non_empty_text("request_id", request_id)
        ensure_non_empty_text("operation_id", operation_id)
        if execution_id is not None:
            ensure_non_empty_text("execution_id", execution_id)

        records: list[ProviderAttribution] = []
        for provider_class in (
            ProviderClass.INTEGRATION,
            ProviderClass.COMMUNICATION,
            ProviderClass.MODEL,
        ):
            provider_id = self._first_healthy_provider_id(provider_registry, provider_class)
            if provider_id is None:
                continue
            records.append(
                self.record_attribution(
                    request_id=request_id,
                    operation_id=operation_id,
                    execution_id=execution_id,
                    provider_id=provider_id,
                    provider_class=provider_class,
                    source=ProviderAttributionSource.HEALTHY_PLANE_RESOLUTION,
                )
            )
        return tuple(records)

    def record_attribution(
        self,
        *,
        request_id: str,
        operation_id: str,
        execution_id: str | None,
        provider_id: str,
        provider_class: ProviderClass,
        source: ProviderAttributionSource,
    ) -> ProviderAttribution:
        """Record one provider attribution after validating explicit identity fields."""
        ensure_non_empty_text("request_id", request_id)
        ensure_non_empty_text("operation_id", operation_id)
        ensure_non_empty_text("provider_id", provider_id)
        if execution_id is not None:
            ensure_non_empty_text("execution_id", execution_id)
        if not isinstance(provider_class, ProviderClass):
            raise RuntimeCoreInvariantError("provider_class must be a ProviderClass value")
        if not isinstance(source, ProviderAttributionSource):
            raise RuntimeCoreInvariantError("source must be a ProviderAttributionSource value")

        now = self._clock()
        evidence_id = stable_identifier(
            "provider-attr-evidence",
            {
                "operation_id": operation_id,
                "provider_id": provider_id,
                "provider_class": provider_class.value,
                "source": source.value,
            },
        )
        attribution_id = stable_identifier(
            "provider-attr",
            {
                "operation_id": operation_id,
                "provider_id": provider_id,
                "provider_class": provider_class.value,
                "evidence_id": evidence_id,
            },
        )
        if attribution_id in self._records:
            return self._records[attribution_id]

        record = ProviderAttribution(
            attribution_id=attribution_id,
            operation_id=operation_id,
            request_id=request_id,
            execution_id=execution_id,
            provider_id=provider_id,
            provider_class=provider_class,
            source=source,
            evidence_id=evidence_id,
            attributed_at=now,
        )
        self._records[attribution_id] = record
        existing_ids = self._operation_index.get(operation_id, ())
        self._operation_index[operation_id] = tuple(sorted(existing_ids + (attribution_id,)))
        return record

    @staticmethod
    def _first_healthy_provider_id(
        provider_registry: ProviderRegistry,
        provider_class: ProviderClass,
    ) -> str | None:
        for provider in provider_registry.list_providers(
            provider_class=provider_class,
            enabled_only=True,
        ):
            health = provider_registry.get_health(provider.provider_id)
            if health is not None and health.status is ProviderHealthStatus.HEALTHY:
                return provider.provider_id
        return None
