"""Purpose: provider attribution ledger for per-operation provider-plane identity.
Governance scope: deterministic attribution of provider ids to runtime operations.
Dependencies: provider attribution contracts, provider routing contracts, provider registry, and invariant helpers.
Invariants:
  - Only enabled, healthy, registered providers can be attributed through plane resolution.
  - Each operation/provider-class pair has at most one attribution record.
  - Ledger mutation is append-only for new attribution identities.
  - Attribution exposes source, source reference, and evidence id instead of implying hidden invocation facts.
"""

from __future__ import annotations

from typing import Callable

from mcoi_runtime.contracts.provider import ProviderClass, ProviderHealthStatus
from mcoi_runtime.contracts.provider_attribution import (
    ProviderAttribution,
    ProviderAttributionSource,
)
from mcoi_runtime.contracts.execution import ExecutionResult
from mcoi_runtime.contracts.provider_routing import RoutingDecision, RoutingOutcome
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

    def source_counts(self) -> dict[str, int]:
        """Return deterministic attribution counts by source."""
        counts = {source.value: 0 for source in ProviderAttributionSource}
        for record in self._records.values():
            counts[record.source.value] += 1
        return counts

    def witness_counters(self) -> dict[str, int]:
        """Return operator-facing provider attribution witness counters."""
        counts = self.source_counts()
        return {
            "provider_attribution_count": self.attribution_count,
            "receipt_attributed_provider_operation_count": counts[ProviderAttributionSource.EXECUTION_RECEIPT.value],
            "routing_attributed_provider_operation_count": counts[ProviderAttributionSource.ROUTING_DECISION.value],
            "plane_attributed_provider_operation_count": counts[
                ProviderAttributionSource.HEALTHY_PLANE_RESOLUTION.value
            ],
        }

    def attribution_witness(self, *, operation_id: str, generated_at: str) -> dict[str, object]:
        """Return a Provider Attribution Witness schema payload for one operation."""
        ensure_non_empty_text("operation_id", operation_id)
        ensure_non_empty_text("generated_at", generated_at)
        records = self.list_for_operation(operation_id)
        source_counts = {source.value: 0 for source in ProviderAttributionSource}
        for record in records:
            source_counts[record.source.value] += 1
        return {
            "witness_id": stable_identifier(
                "provider-attribution-witness",
                {
                    "operation_id": operation_id,
                    "generated_at": generated_at,
                    "record_count": len(records),
                },
            ),
            "operation_id": operation_id,
            "provider_attribution_count": len(records),
            "receipt_attributed_provider_operation_count": source_counts[
                ProviderAttributionSource.EXECUTION_RECEIPT.value
            ],
            "routing_attributed_provider_operation_count": source_counts[
                ProviderAttributionSource.ROUTING_DECISION.value
            ],
            "plane_attributed_provider_operation_count": source_counts[
                ProviderAttributionSource.HEALTHY_PLANE_RESOLUTION.value
            ],
            "provider_attributions": [
                {
                    "provider_id": record.provider_id,
                    "provider_class": record.provider_class.value,
                    "source": record.source.value,
                    "source_ref_id": record.source_ref_id,
                    "evidence_id": record.evidence_id,
                }
                for record in records
            ],
            "generated_at": generated_at,
        }

    def list_for_operation(self, operation_id: str) -> tuple[ProviderAttribution, ...]:
        """Return records for an operation in provider-class order."""
        ensure_non_empty_text("operation_id", operation_id)
        attribution_ids = self._operation_index.get(operation_id, ())
        return tuple(
            sorted(
                (self._records[attribution_id] for attribution_id in attribution_ids),
                key=lambda record: (record.provider_class.value, record.provider_id, record.source.value),
            )
        )

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
                    source_ref_id=operation_id,
                )
            )
        return tuple(records)

    def attribute_routing_decision(
        self,
        *,
        request_id: str,
        operation_id: str,
        execution_id: str | None,
        decision: RoutingDecision,
        provider_registry: ProviderRegistry,
    ) -> ProviderAttribution:
        """Attribute an operation to the provider selected by a routing decision."""
        provider_class = self._provider_class_for(provider_registry, decision.selected_provider_id)
        return self.record_attribution(
            request_id=request_id,
            operation_id=operation_id,
            execution_id=execution_id,
            provider_id=decision.selected_provider_id,
            provider_class=provider_class,
            source=ProviderAttributionSource.ROUTING_DECISION,
            source_ref_id=decision.decision_id,
        )

    def attribute_routing_outcome(
        self,
        *,
        request_id: str,
        operation_id: str,
        execution_id: str | None,
        outcome: RoutingOutcome,
        provider_registry: ProviderRegistry,
    ) -> ProviderAttribution:
        """Attribute an operation to the provider named by a routing outcome receipt."""
        provider_class = self._provider_class_for(provider_registry, outcome.provider_id)
        return self.record_attribution(
            request_id=request_id,
            operation_id=operation_id,
            execution_id=execution_id,
            provider_id=outcome.provider_id,
            provider_class=provider_class,
            source=ProviderAttributionSource.EXECUTION_RECEIPT,
            source_ref_id=outcome.outcome_id,
        )

    def attribute_execution_result_receipt(
        self,
        *,
        request_id: str,
        operation_id: str,
        execution_result: ExecutionResult,
        provider_registry: ProviderRegistry,
    ) -> tuple[ProviderAttribution, ...]:
        """Attribute an operation from provider receipt metadata on an execution result."""
        metadata = execution_result.metadata
        provider_id = metadata.get("provider_id")
        source_ref_id = metadata.get("provider_source_ref_id")
        provider_class_value = metadata.get("provider_class")
        if provider_id is None and source_ref_id is None and provider_class_value is None:
            return ()
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise RuntimeCoreInvariantError("execution receipt provider_id must be a non-empty string")
        if not isinstance(source_ref_id, str) or not source_ref_id.strip():
            raise RuntimeCoreInvariantError("execution receipt provider_source_ref_id must be a non-empty string")
        provider_class = self._provider_class_for(provider_registry, provider_id)
        if provider_class_value is not None and provider_class.value != provider_class_value:
            raise RuntimeCoreInvariantError("execution receipt provider_class must match registry provider class")
        return (
            self.record_attribution(
                request_id=request_id,
                operation_id=operation_id,
                execution_id=execution_result.execution_id,
                provider_id=provider_id,
                provider_class=provider_class,
                source=ProviderAttributionSource.EXECUTION_RECEIPT,
                source_ref_id=source_ref_id,
            ),
        )

    def record_attribution(
        self,
        *,
        request_id: str,
        operation_id: str,
        execution_id: str | None,
        provider_id: str,
        provider_class: ProviderClass,
        source: ProviderAttributionSource,
        source_ref_id: str,
    ) -> ProviderAttribution:
        """Record one provider attribution after validating explicit identity fields."""
        ensure_non_empty_text("request_id", request_id)
        ensure_non_empty_text("operation_id", operation_id)
        ensure_non_empty_text("provider_id", provider_id)
        ensure_non_empty_text("source_ref_id", source_ref_id)
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
                "source_ref_id": source_ref_id,
            },
        )
        attribution_id = stable_identifier(
            "provider-attr",
            {
                "operation_id": operation_id,
                "provider_id": provider_id,
                "provider_class": provider_class.value,
                "source": source.value,
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
            source_ref_id=source_ref_id,
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

    @staticmethod
    def _provider_class_for(
        provider_registry: ProviderRegistry,
        provider_id: str,
    ) -> ProviderClass:
        provider = provider_registry.get_provider(provider_id)
        if provider is None:
            raise RuntimeCoreInvariantError("attributed provider must be registered")
        return provider.provider_class
