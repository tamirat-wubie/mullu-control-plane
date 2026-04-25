"""Purpose: verify provider attribution contracts and ledger behavior.
Governance scope: provider identity attribution tests only.
Dependencies: provider contracts, provider registry, and provider attribution ledger.
Invariants: attribution is deterministic, registry-bound, and never assigned to unhealthy providers.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.provider import (
    CredentialScope,
    ProviderClass,
    ProviderDescriptor,
    ProviderHealthStatus,
)
from mcoi_runtime.contracts.provider_attribution import (
    ProviderAttribution,
    ProviderAttributionSource,
)
from mcoi_runtime.contracts.execution import ExecutionOutcome, ExecutionResult
from mcoi_runtime.core.provider_attribution import ProviderAttributionLedger
from mcoi_runtime.core.provider_registry import ProviderRegistry


FIXED_CLOCK = "2026-04-25T12:00:00+00:00"


def _registry() -> ProviderRegistry:
    return ProviderRegistry(clock=lambda: FIXED_CLOCK)


def _ledger() -> ProviderAttributionLedger:
    return ProviderAttributionLedger(clock=lambda: FIXED_CLOCK)


def _register_provider(
    registry: ProviderRegistry,
    provider_id: str,
    provider_class: ProviderClass,
    *,
    enabled: bool = True,
) -> None:
    registry.register(
        ProviderDescriptor(
            provider_id=provider_id,
            name=f"provider-{provider_id}",
            provider_class=provider_class,
            credential_scope_id=f"scope-{provider_id}",
            enabled=enabled,
        ),
        CredentialScope(
            scope_id=f"scope-{provider_id}",
            provider_id=provider_id,
        ),
    )


def test_provider_attribution_contract_rejects_empty_identity() -> None:
    with pytest.raises(ValueError, match="attribution_id must be a non-empty string"):
        ProviderAttribution(
            attribution_id="",
            operation_id="operation-1",
            request_id="request-1",
            execution_id="execution-1",
            provider_id="provider-1",
            provider_class=ProviderClass.MODEL,
            source=ProviderAttributionSource.HEALTHY_PLANE_RESOLUTION,
            source_ref_id="operation-1",
            evidence_id="evidence-1",
            attributed_at=FIXED_CLOCK,
        )


def test_attribute_healthy_planes_records_enabled_healthy_provider_per_class() -> None:
    registry = _registry()
    ledger = _ledger()
    _register_provider(registry, "provider-model", ProviderClass.MODEL)
    _register_provider(registry, "provider-int", ProviderClass.INTEGRATION)
    registry.record_success("provider-model")
    registry.record_success("provider-int")

    records = ledger.attribute_healthy_planes(
        request_id="request-1",
        operation_id="execution-1",
        execution_id="execution-1",
        provider_registry=registry,
    )

    assert ledger.attribution_count == 2
    assert {record.provider_id for record in records} == {"provider-int", "provider-model"}
    assert {record.provider_class for record in records} == {ProviderClass.INTEGRATION, ProviderClass.MODEL}
    assert all(record.source is ProviderAttributionSource.HEALTHY_PLANE_RESOLUTION for record in records)
    assert all(record.source_ref_id == "execution-1" for record in records)
    assert all(record.evidence_id.startswith("provider-attr-evidence-") for record in records)


def test_attribute_healthy_planes_skips_disabled_and_unhealthy_providers() -> None:
    registry = _registry()
    ledger = _ledger()
    _register_provider(registry, "provider-disabled", ProviderClass.MODEL, enabled=False)
    _register_provider(registry, "provider-unhealthy", ProviderClass.MODEL)
    registry.record_failure("provider-unhealthy", "network_error")

    records = ledger.attribute_healthy_planes(
        request_id="request-2",
        operation_id="execution-2",
        execution_id="execution-2",
        provider_registry=registry,
    )

    assert records == ()
    assert ledger.attribution_count == 0
    assert registry.get_health("provider-unhealthy").status is ProviderHealthStatus.DEGRADED


def test_attribute_healthy_planes_is_idempotent_for_same_operation() -> None:
    registry = _registry()
    ledger = _ledger()
    _register_provider(registry, "provider-model", ProviderClass.MODEL)
    registry.record_success("provider-model")

    first = ledger.attribute_healthy_planes(
        request_id="request-3",
        operation_id="execution-3",
        execution_id="execution-3",
        provider_registry=registry,
    )
    second = ledger.attribute_healthy_planes(
        request_id="request-3",
        operation_id="execution-3",
        execution_id="execution-3",
        provider_registry=registry,
    )

    assert first == second
    assert ledger.attribution_count == 1
    assert ledger.list_for_operation("execution-3") == first


def test_attribute_execution_result_receipt_records_provider_receipt_source() -> None:
    registry = _registry()
    ledger = _ledger()
    _register_provider(registry, "provider-http", ProviderClass.INTEGRATION)
    execution_result = ExecutionResult(
        execution_id="execution-receipt-1",
        goal_id="goal-receipt-1",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=(),
        assumed_effects=(),
        started_at=FIXED_CLOCK,
        finished_at=FIXED_CLOCK,
        metadata={
            "provider_id": "provider-http",
            "provider_class": "integration",
            "provider_source_ref_id": "connector-receipt-1",
        },
    )

    records = ledger.attribute_execution_result_receipt(
        request_id="request-receipt-1",
        operation_id="execution-receipt-1",
        execution_result=execution_result,
        provider_registry=registry,
    )

    assert len(records) == 1
    assert records[0].provider_id == "provider-http"
    assert records[0].provider_class is ProviderClass.INTEGRATION
    assert records[0].source is ProviderAttributionSource.EXECUTION_RECEIPT
    assert records[0].source_ref_id == "connector-receipt-1"
